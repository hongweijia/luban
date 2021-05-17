#!/usr/bin/python
import sys, os.path, time, stat, socket, base64,json
import configparser
import shutil
import yapl.Utilities as Utilities
from subprocess import call,check_output, check_call, CalledProcessError, Popen, PIPE
from os import chmod, environ
from yapl.Trace import Trace, Level
from yapl.Exceptions import MissingArgumentException

TR = Trace(__name__)
StackParameters = {}
StackParameterNames = []
class CPDInstall(object):
    ArgsSignature = {
                    '--region': 'string',
                    '--stack-name': 'string',
                    '--stackid': 'string',
                    '--logfile': 'string',
                    '--loglevel': 'string',
                    '--trace': 'string'
                   }

    def __init__(self):
        """
        Constructor

        NOTE: Some instance variable initialization happens in self._init() which is 
        invoked early in main() at some point after _getStackParameters().
        """
        object.__init__(self)
        self.home = os.path.expanduser("/ibm")
        self.logsHome = os.path.join(self.home,"logs")
         
    #endDef 
    def _getArg(self,synonyms,args,default=None):
        """
        Return the value from the args dictionary that may be specified with any of the
        argument names in the list of synonyms.

        The synonyms argument may be a Jython list of strings or it may be a string representation
        of a list of names with a comma or space separating each name.

        The args is a dictionary with the keyword value pairs that are the arguments
        that may have one of the names in the synonyms list.

        If the args dictionary does not include the option that may be named by any
        of the given synonyms then the given default value is returned.

        NOTE: This method has to be careful to make explicit checks for value being None
        rather than something that is just logically false.  If value gets assigned 0 from
        the get on the args (command line args) dictionary, that appears as false in a
        condition expression.  However 0 may be a legitimate value for an input parameter
        in the args dictionary.  We need to break out of the loop that is checking synonyms
        as well as avoid assigning the default value if 0 is the value provided in the
        args dictionary.
        """
        
        value = None
        if (type(synonyms) != type([])):
            synonyms = Utilities.splitString(synonyms)
        #endIf

        for name in synonyms:
            value = args.get(name)
            if (value != None):
                break
        #endIf
        #endFor

        if (value == None and default != None):
         value = default
        #endIf

        return value
    #endDef

    def _configureTraceAndLogging(self,traceArgs):
        """
        Return a tuple with the trace spec and logFile if trace is set based on given traceArgs.

        traceArgs is a dictionary with the trace configuration specified.
            loglevel|trace <tracespec>
            logfile|logFile <pathname>

        If trace is specified in the trace arguments then set up the trace.
        If a log file is specified, then set up the log file as well.
        If trace is specified and no log file is specified, then the log file is
        set to "trace.log" in the current working directory.
        """
        logFile = self._getArg(['logFile','logfile'], traceArgs)
        if (logFile):
            TR.appendTraceLog(logFile)
        #endIf

        trace = self._getArg(['trace', 'loglevel'], traceArgs)

        if (trace):
            if (not logFile):
                TR.appendTraceLog('trace.log')
            #endDef

        TR.configureTrace(trace)
        #endIf
        return (trace,logFile)
    #endDef
   
 
    def installCPD(self,icpdInstallLogFile):
        """
        creates a OC project with user defined name
        Downloads binary file from S3 and extracts it to /ibm folder
        installs user selected services using transfer method

        """

        methodName = "installCPD"
        os.chmod(self.installer_path,stat.S_IEXEC)
      
        default_route = "oc get route default-route -n openshift-image-registry --template='{{ .spec.host }}'"
        TR.info(methodName,"Get default route  %s"%default_route)
        try:
            self.regsitry = check_output(['bash','-c', default_route]) 
            TR.info(methodName,"Completed %s command with return value %s" %(default_route,self.regsitry))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        try:
            oc_login = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
            retcode = call(oc_login,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Log in to OC with admin user %s"%retcode)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        oc_new_project ="oc new-project " + self.namespace
        try:
            retcode = call(oc_new_project,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Create new project with user defined project name %s,retcode=%s" %(self.namespace,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        litestart = Utilities.currentTimeMillis()
        TR.info(methodName,"Start installing Lite package")
        self.installAssembliesAirgap("lite",icpdInstallLogFile)
        liteend = Utilities.currentTimeMillis()
        self.printTime(litestart, liteend, "Installing Lite")

        get_cpd_route_cmd = "oc get route -n "+self.namespace+ " | grep '"+self.namespace+"' | awk '{print $2}'"
        TR.info(methodName, "Get CPD URL")
        try:
            self.cpdURL = check_output(['bash','-c', get_cpd_route_cmd]) 
            TR.info(methodName, "CPD URL retrieved %s"%self.cpdURL)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        if(self.installSpark == "True"):
            TR.info(methodName,"Start installing Spark AE package")
            sparkstart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("spark",icpdInstallLogFile)
            sparkend = Utilities.currentTimeMillis()
            TR.info(methodName,"Spark AE  package installation completed")
            self.printTime(sparkstart, sparkend, "Installing Spark AE")   

        if(self.installDV == "True"):
            TR.info(methodName,"Start installing DV package")
            dvstart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("dv",icpdInstallLogFile)
            dvend = Utilities.currentTimeMillis()
            TR.info(methodName,"DV package installation completed")
            self.printTime(dvstart, dvend, "Installing DV")    
        
        if(self.installWSL == "True"):

            TR.info(methodName,"Start installing WSL package")
            wslstart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("wsl",icpdInstallLogFile)
            wslend = Utilities.currentTimeMillis()
            TR.info(methodName,"WSL package installation completed")
            self.printTime(wslstart, wslend, "Installing WSL")
        
        if(self.installWML == "True"):
            TR.info(methodName,"Start installing WML package")
            wmlstart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("wml",icpdInstallLogFile)
            wmlend = Utilities.currentTimeMillis()
            TR.info(methodName,"WML package installation completed")
            self.printTime(wmlstart, wmlend, "Installing WML")
        
        if(self.installWKC == "True"):
            TR.info(methodName,"Start installing WKC package")
            wkcstart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("wkc",icpdInstallLogFile)
            wkcend = Utilities.currentTimeMillis()
            TR.info(methodName,"WKC package installation completed")
            self.printTime(wkcstart, wkcend, "Installing WKC")

        if(self.installOSWML == "True"):
            TR.info(methodName,"Start installing AI Openscale package")
            aiostart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("aiopenscale",icpdInstallLogFile)
            aioend = Utilities.currentTimeMillis()
            TR.info(methodName,"AI Openscale package installation completed")
            self.printTime(aiostart, aioend, "Installing AI Openscale")    

        if(self.installCDE == "True"):
            TR.info(methodName,"Start installing Cognos Dashboard package")
            cdestart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("cde",icpdInstallLogFile)
            cdeend = Utilities.currentTimeMillis()
            TR.info(methodName,"Cognos Dashboard package installation completed")
            self.printTime(cdestart, cdeend, "Installing Cognos Dashboard")  

        
        if(self.installRStudio == "True"):
            TR.info(methodName,"Start installing RStudio package")
            rstudiostart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("rstudio",icpdInstallLogFile)
            rstudioend = Utilities.currentTimeMillis()
            TR.info(methodName,"RStudio package installation completed")
            self.printTime(rstudiostart, rstudioend, "Installing RStudio")      
        
        if(self.installSPSS == "True"):
            TR.info(methodName,"Start installing SPSS package")
            spssstart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("spss-modeler",icpdInstallLogFile)
            spssend = Utilities.currentTimeMillis()
            TR.info(methodName,"SPSS package installation completed")
            self.printTime(spssstart, spssend, "Installing SPSS")
        
        if(self.installStreams == "True"):
            TR.info(methodName,"Start installing Streams package")
            streamsstart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("streams",icpdInstallLogFile)
            streamssend = Utilities.currentTimeMillis()
            TR.info(methodName,"Streams package installation completed")
            self.printTime(streamsstart, streamsend, "Installing Streams")

        if(self.installRuntimeGPUPy36 == "True"):
            TR.info(methodName,"Start installing GPUPy36 package")
            gpupy36start = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("runtime-addon-gpupy36",icpdInstallLogFile)
            gpupy36end = Utilities.currentTimeMillis()
            TR.info(methodName,"GPUPy36 package installation completed")
            self.printTime(gpupy36start, gpupy36end, "Installing GPUPy36")
        
        if(self.installRuntimeR36 == "True"):
            TR.info(methodName,"Start installing RuntimeR36 package")
            r36start = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("runtime-addon-r36",icpdInstallLogFile)
            r36end = Utilities.currentTimeMillis()
            TR.info(methodName,"R36 package installation completed")
            self.printTime(r36start, r36end, "Installing R36")
        
        if(self.installHEE == "True"):
            TR.info(methodName,"Start installing HEE package")
            heestart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("hadoop-addon",icpdInstallLogFile)
            heeend = Utilities.currentTimeMillis()
            TR.info(methodName,"HEE package installation completed")
            self.printTime(heestart, heeend, "Installing HEE")
        
        if(self.installDODS == "True"):
            TR.info(methodName,"Start installing DODS package")
            dodsstart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("dods",icpdInstallLogFile)
            dodsend = Utilities.currentTimeMillis()
            TR.info(methodName,"DODS package installation completed")
            self.printTime(dodsstart, dodsend, "Installing DODS")
        
        if(self.installOSG == "True"):
            TR.info(methodName,"Start installing OSG package")
            osgstart = Utilities.currentTimeMillis()
            self.installAssembliesAirgap("osg",icpdInstallLogFile)
            osgsend = Utilities.currentTimeMillis()
            TR.info(methodName,"OSG package installation completed")
            self.printTime(osgstart, osgend, "Installing OSG")


        TR.info(methodName,"Installed all packages.")
    #endDef 

   
    def printTime(self, beginTime, endTime, text):
        """
        method to capture time elapsed for each event during installation
        """
        methodName = "printTime"
        elapsedTime = (endTime - beginTime)/1000
        etm, ets = divmod(elapsedTime,60)
        eth, etm = divmod(etm,60) 
        TR.info(methodName,"Elapsed time (hh:mm:ss): %d:%02d:%02d for %s" % (eth,etm,ets,text))
    #endDef

    def getToken(self,icpdInstallLogFile):
        """
        method to get sa token to be used to push and pull from local docker registry
        """
        methodName = "getToken"
        create_sa_cmd = "oc create serviceaccount cpdtoken"
        TR.info(methodName,"Create service account cpdtoken %s"%create_sa_cmd)
        try:
            retcode = call(create_sa_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Created service account cpdtoken %s"%retcode)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        addrole_cmd = "oc policy add-role-to-user admin system:serviceaccount:"+self.namespace+":cpdtoken"
        TR.info(methodName," Add role to service account %s"%addrole_cmd)
        try:
            retcode = call(addrole_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Role added to service account %s"%retcode)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        get_token_cmd = "oc serviceaccounts get-token cpdtoken"
        TR.info(methodName,"Retrieve token from service account %s"%get_token_cmd)
        return check_output(['bash','-c', get_token_cmd])
    #endDef  

    def changeNodeSettings(self, icpdInstallLogFile):
        methodName = "changeNodeSettings"
        TR.info(methodName,"  Start changing node settings of Openshift Container Platform")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        

        crio_conf   = "./templates/cpd/crio.conf"
        crio_mc     = "./templates/cpd/crio-mc.yaml"
        
        
        crio_config_data = base64.b64encode(self.readFileContent(crio_conf))
        self.updateTemplateFile(crio_mc, '${crio-config-data}', crio_config_data)

        create_crio_mc  = "oc create -f "+crio_mc

        TR.info(methodName,"Creating crio mc with command %s"%create_crio_mc)
        try:
            crio_retcode = check_output(['bash','-c', create_crio_mc]) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        TR.info(methodName,"Created Crio mc with command %s returned %s"%(create_crio_mc,crio_retcode))
        
        """
        "oc create -f ${local.ocptemplates}/wkc-sysctl-mc.yaml",
        "oc create -f ${local.ocptemplates}/security-limits-mc.yaml",
        """
        sysctl_cmd =  "oc create -f ./templates/cpd/wkc-sysctl-mc.yaml"
        TR.info(methodName,"Create SystemCtl Machine config")
        try:
            retcode = check_output(['bash','-c', sysctl_cmd]) 
            TR.info(methodName,"Created  SystemCtl Machine config %s" %retcode) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        secLimits_cmd =  "oc create -f ./templates/cpd/security-limits-mc.yaml"
        TR.info(methodName,"Create Security Limits Machine config")
        try:
            retcode = check_output(['bash','-c', secLimits_cmd]) 
            TR.info(methodName,"Created  Security Limits Machine config %s" %retcode)  
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))  
        time.sleep(600)

        TR.info(methodName,"  Completed node settings of Openshift Container Platform")
    #endDef

    def updateTemplateFile(self, source, placeHolder, value):
        """
        method to update placeholder values in templates
        """
        source_file = open(source).read()
        source_file = source_file.replace(placeHolder, value)
        updated_file = open(source, 'w')
        updated_file.write(source_file)
        updated_file.close()
    #endDef    
    def readFileContent(self,source):
        file = open(source,mode='r')
        content = file.read()
        file.close()
        return content.rstrip()

    def installAssemblies(self, assembly, icpdInstallLogFile):
        """
        method to install assemlies
        for each assembly this method will execute adm command to apply all prerequistes
        Images will be pushed to local registry
        Installation will be done for the assembly using local registry
        """
        methodName = "installAssemblies"

        registry = self.regsitry+"/"+self.namespace
        apply_cmd = self.installer_path + " adm -r " + self.repo_path + " -a "+assembly+"  -n " + self.namespace+" --accept-all-licenses --apply | tee /ibm/logs/"+assembly+"_apply.log"
        TR.info(methodName,"Execute apply command for assembly %s"%apply_cmd)
        try:
            retcode = call(apply_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed apply command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

        install_cmd = self.installer_path + " install --storageclass " + self.storage_class + " --override-config portworx -r " + self.repo_path + " --assembly "+assembly+" --arch x86_64 -n "+self.namespace+" --transfer-image-to "+registry+" --cluster-pull-username="+ self.ocp_admin_user + " --cluster-pull-password="+self.ocToken+" --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/"+self.namespace+" --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/" +assembly+"_install.log"

        try:     
            retcode = call(install_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Execute install command for assembly %s returned %s"%(assembly,retcode))  
        except CalledProcessError as e:
            TR.error(methodName,"Exception while installing service %s with message %s" %(assembly,e))
            self.rc = 1

    def installAssembliesAirgap(self, assembly, icpdInstallLogFile):
        """
        method to install assemlies
        for each assembly this method will execute adm command to apply all prerequistes
        Images will be pushed to local registry
        Installation will be done for the assembly using local registry
        """
        methodName = "installAssembliesAirgap"

        registry = self.regsitry+"/"+self.namespace
  
        
        push_cmd = self.installer_path + " preload-images --assembly " + assembly + " --action push --load-from " + self.load_from + " --transfer-image-to " + registry + " --target-registry-username "+ self.ocp_admin_user + " --target-registry-password "+ self.ocToken + " --insecure-skip-tls-verify --accept-all-licenses | tee "+self.log_dir +"/"+assembly+"_push.log"
        TR.info(methodName,"Execute push command for assembly %s"%push_cmd)
        try:
            retcode = call(push_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed push command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

        apply_cmd = self.installer_path +" adm --assembly " + assembly + " --latest-dependency -n "+self.namespace+ " --load-from " + self.load_from + " --accept-all-licenses --apply | tee "+self.log_dir +"/"+assembly+"_apply.log"
        TR.info(methodName,"Execute apply command for assembly %s"%apply_cmd)
        try:
            retcode = call(apply_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed apply command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

        install_cmd = self.installer_path + " install --assembly " + assembly + " --latest-dependency --arch x86_64 -n " + self.namespace + " --storageclass " + self.storage_class + " --override-config portworx --load-from " + self.load_from +" --cluster-pull-username " +self.ocp_admin_user + " --cluster-pull-password " + self.ocToken + " --cluster-pull-prefix image-registry.openshift-image-registry.svc:5000/" + self.namespace + " --verbose --accept-all-licenses --insecure-skip-tls-verify | tee "+self.log_dir +"/"+assembly+"_install.log"
        TR.info(methodName,"Execute install command for assembly %s"%install_cmd)
        try:
            retcode = call(install_cmd,shell=True, stdout=icpdInstallLogFile)
            TR.info(methodName,"Executed install command for assembly %s returned %s"%(assembly,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"Exception while installing service %s with message %s" %(assembly,e))
            self.rc = 1


 
    def validateInstall(self, icpdInstallLogFile):
        """
            This method is used to validate the installation at the end. At times some services fails and it is not reported. 
            We use this method to check if cpd operator is up and running. We will then get the helm list of deployed services and validate for each of the services selected by user. IF the count adds up to the defined count then installation is successful. Else  will be flagged it as failure back to cloud Formation.
        """

        methodName = "validateInstall"
        count = 3
        TR.info(methodName,"Validate Installation status")
        if(self.installDV == "True"):
            count = count+1
        if(self.installOSWML == "True"):
            count = count+1    
        if(self.installSpark == "True"):
            count = count+1    
        if(self.installWKC == "True"):
            count = count+6
        if(self.installCDE == "True"):
            count = count+1
        if(self.installWML == "True"):
            count = count+2
        if(self.installWSL == "True"):
            count = count+4            

        # CCS Count
        if(self.installCDE == "True" or self.installWKC == "True" or self.installWSL == "True" or self.installWML == "True"):
            count = count+8
        # DR count    
        if(self.installWSL == "True" or self.installWKC == "True"):
            count = count+1                

        operator_pod = "oc get pods | grep cpd-install-operator | awk '{print $1}'"
        operator_status = "oc get pods | grep cpd-install-operator | awk '{print $3}'"
        validate_cmd = "oc exec -it $(oc get pods | grep cpd-install-operator | awk '{print $1}') -- helm list --tls"
        operator = check_output(['bash','-c',operator_pod])
        TR.info(methodName,"Operator pod %s"%operator)
        if(operator == ""):
            self.rc = 1
            return
        op_status = check_output(['bash','-c',operator_status])
        TR.info(methodName,"Operator pod status is %s"%op_status)
        if(op_status.rstrip()!="Running"):
            self.rc = 1
            return   
        install_status = check_output(['bash','-c',validate_cmd])
        TR.info(methodName,"Installation status is %s"%install_status)
        #TR.info(methodName,"Actual Count is %s Deployed count is %s"%(count,install_status.count("DEPLOYED")))
        #if(install_status.count("DEPLOYED")< count):
        #    self.rc = 1
        #    TR.info(methodName,"Installation Deployed count  is %s"%install_status.count("DEPLOYED"))
        #    return   

    #endDef          
    
    def _loadConf(self):
        methodName = "loadConf"
        TR.info(methodName,"Start load installation configuration")
        config = configparser.ConfigParser()
        config.read('../cpd_install.conf')

        self.ocp_admin_user = config['install']['ocp_admin_user']
        self.ocp_admin_password = config['install']['ocp_admin_password']
        self.load_from = config['install']['load_from']
        self.log_dir = config['install']['log_dir']
        self.overall_log_file = config['install']['overall_log_file']
        self.installer_path = config['install']['installer_path']
        self.repo_path = config['install']['repo_path']
        self.installWSL = config['install']['installWSL']
        self.installWML = config['install']['installWML']
        self.installWKC = config['install']['installWKC']
        self.installSpark = config['install']['installSpark']
        self.installCDE = config['install']['installCDE']
        self.installDV = config['install']['installDV']
        self.installOSWML = config['install']['installOSWML']
        self.installRStudio = config['install']['installRStudio']
        self.installSPSS = config['install']['installSPSS']
        self.installStreams = config['install']['installStreams']
        self.installRuntimeGPUPy36 = config['install']['installRuntimeGPUPy36']
        self.installRuntimeR36 = config['install']['installRuntimeR36']
        self.installHEE = config['install']['installHEE']
        self.installDODS = config['install']['installDODS']
        self.installOSG = config['install']['installOSG']
        self.storage_class = config['install']['storage_class']        
        self.namespace = config['install']['namespace']
        TR.info(methodName,"Load installation configuration completed")
        TR.info(methodName,"Installation configuration:" + self.ocp_admin_user + "-" + self.ocp_admin_password  + "-" + self.installer_path + "-" + self.installWSL)
    #endDef

    def main(self,argv):
        methodName = "main"
        self.rc = 0
        try:
            beginTime = Utilities.currentTimeMillis()
           
            self._loadConf()   
      
            if (self.overall_log_file):
                TR.appendTraceLog(self.overall_log_file)   

            logFilePath = os.path.join(self.logsHome,"icpd_install.log")

            with open(logFilePath,"a+") as icpdInstallLogFile:  
                ocpstart = Utilities.currentTimeMillis()
                self.changeNodeSettings(icpdInstallLogFile)
                TR.info("debug","Finishd the node settings")
                ocpend = Utilities.currentTimeMillis()
                self.printTime(ocpstart, ocpend, "Chaning node settings")

                if(self.installOSWML == "True"):
                    self.installWML="True"
                
                TR.info("debug","installWKC= %s" %self.installWKC)
                TR.info("debug","installWSL= %s" %self.installWSL)
                TR.info("debug","installDV= %s" %self.installDV)
                TR.info("debug","installWML= %s" %self.installWML)
                TR.info("debug","installOSWML= %s" %self.installOSWML)
                TR.info("debug","installCDE= %s" %self.installCDE)
                TR.info("debug","installSpark= %s" %self.installSpark)
                TR.info("debug","installRStudio= %s" %self.installRStudio)
                TR.info("debug","installSPSS= %s" %self.installSPSS)
                TR.info("debug","installStreams= %s" %self.installStreams)
                TR.info("debug","installRuntimeGPUPy36= %s" %self.installRuntimeGPUPy36)
                TR.info("debug","installRuntimeR36= %s" %self.installRuntimeR36)
                TR.info("debug","installHEE= %s" %self.installHEE)
                TR.info("debug","installDODS= %s" %self.installDODS)
                TR.info("debug","installOSG= %s" %self.installOSG)

               
                getTokenCmd = "oc whoami -t"

                try:
                    self.ocToken = check_output(['bash','-c', getTokenCmd])
                    self.ocToken = self.ocToken.strip('\n')
                    TR.info(methodName,"Completed %s command with return value %s" %(getTokenCmd,self.ocToken))
                except CalledProcessError as e:
                    TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))

                self.installCPD(icpdInstallLogFile)
                
                self.installStatus = "CPD Installation completed"
                TR.info("debug","Installation status - %s" %self.installStatus)


                self.validateInstall(icpdInstallLogFile)


                self.installStatus = "Finished validating installation"
                TR.info("debug","Installation status - %s" %self.installStatus)

            #endWith    
            
        except Exception as e:
            TR.error(methodName,"Exception with message %s" %e)
            self.rc = 1

        endTime = Utilities.currentTimeMillis()
        elapsedTime = (endTime - beginTime)/1000
        etm, ets = divmod(elapsedTime,60)
        eth, etm = divmod(etm,60) 

        if (self.rc == 0):
            success = 'true'
            status = 'SUCCESS'
            TR.info(methodName,"SUCCESS END CPD Quickstart.  Elapsed time (hh:mm:ss): %d:%02d:%02d" % (eth,etm,ets))
        else:
            success = 'false'
            status = 'FAILURE: Check logs on the Boot node in /ibm/logs/icpd_install.log and /ibm/logs/post_install.log'
            TR.info(methodName,"FAILED END CPD Quickstart.  Elapsed time (hh:mm:ss): %d:%02d:%02d" % (eth,etm,ets))
        #endIf                                            
    #end Def    
#endClass
if __name__ == '__main__':
  mainInstance = CPDInstall()
  mainInstance.main(sys.argv)
#endIf

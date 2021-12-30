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
        #self.home = os.path.expanduser("/ibm")
        #self.logsHome = os.path.join(self.home,"logs")
        os.chdir(os.path.dirname(__file__))
        print(os.getcwd())
        self.logsHome = os.path.join(os.getcwd(),"logs")
        isExist = os.path.exists(self.logsHome)
        if not isExist:
            os.makedirs(self.logsHome)
         
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

    def changeNodeSettings(self, icpdInstallLogFile):
        methodName = "changeNodeSettings"
        TR.info(methodName,"  Start changing node settings of Openshift Container Platform")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        crio_conf   = "./templates/cpd/crio.conf"
        crio_mc     = "./templates/cpd/crio-mc.yaml"
        
        crio_config_data = base64.b64encode(self.readFileContent(crio_conf).encode('ascii')).decode("ascii")
        TR.info(methodName,"encode crio.conf to be base64 string")
        self.updateTemplateFile(crio_mc, '${crio-config-data}', crio_config_data)

        create_crio_mc  = "oc apply -f "+crio_mc

        TR.info(methodName,"Creating crio mc with command %s"%create_crio_mc)
        try:
            crio_retcode = check_output(['bash','-c', create_crio_mc]) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        TR.info(methodName,"Created CRIO mc with command %s returned %s"%(create_crio_mc,crio_retcode))
        
        TR.info(methodName,"Wait 15 minutes for CRIO Machine Config to be completed")
        time.sleep(900)
        """
        "oc apply -f ${local.ocptemplates}/kernel-params_node-tuning-operator.yaml"
        """
        setting_kernel_param_cmd =  "oc apply -f ./templates/cpd/kernel-params_node-tuning-operator.yaml"
        TR.info(methodName,"Create Node Tuning Operator for kernel parameter")
        try:
            retcode = check_output(['bash','-c', setting_kernel_param_cmd]) 
            TR.info(methodName,"Created Node Tuning Operator for kernel parameter %s" %retcode) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        TR.info(methodName,"  Completed node settings of Openshift Container Platform")
    #endDef

    def configImagePull(self, icpdInstallLogFile):
        methodName = "configImagePull"
        TR.info(methodName,"  Start configuring image pull of Openshift Container Platform")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        set_global_pull_secret_command  = "./setup-global-pull-secret.sh " + self.image_registry_url + " " + self.image_registry_user  + " " + self.image_registry_password

        TR.info(methodName,"Setting global pull secret with command %s"%set_global_pull_secret_command)
        try:
            crio_retcode = check_output(['bash','-c', set_global_pull_secret_command]) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        TR.info(methodName,"Setting global pull secret with command %s returned %s"%(set_global_pull_secret_command,crio_retcode))
        
        """
        "oc apply -f ${local.ocptemplates}/image_content_source_policy.yaml"
        """

        image_content_source_policy_cmd = "./setup-img-content-source-policy.sh " + self.image_registry_url
        TR.info(methodName,"Create image content source policy")
        try:
            retcode = check_output(['bash','-c', image_content_source_policy_cmd]) 
            TR.info(methodName,"Create image content source policy %s" %retcode) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    

        time.sleep(900)

        TR.info(methodName,"  Completed image pull related setting")
    #endDef
    
    def configDb2Kubelet(self, icpdInstallLogFile):
        methodName = "configDb2Kubelet"
        TR.info(methodName,"  Start configing Db2 Kubelet of Openshift Container Platform")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        db2_kubelet_config_cmd =  "oc apply -f ./templates/cpd/db2-kubelet-config-mc.yaml"
        TR.info(methodName,"Configure kubelet to allow Db2U to make syscalls as needed.")
        try:
            retcode = check_output(['bash','-c', db2_kubelet_config_cmd]) 
            TR.info(methodName,"Configured kubelet to allow Db2U to make syscalls %s" %retcode)  
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))  
        
        db2_kubelet_config_label_cmd =  "oc label machineconfigpool worker db2u-kubelet=sysctl"
        TR.info(methodName,"Update the label on the machineconfigpool.")
        try:
            retcode = check_output(['bash','-c', db2_kubelet_config_label_cmd]) 
            TR.info(methodName,"Updated the label on the machineconfigpool %s" %retcode)  
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))  
  
        TR.info(methodName,"Wait 10 minutes for Db2U Kubelet Config to be completed")
        time.sleep(600)

        TR.info(methodName,"  Completed config of Db2 Kubelet of Openshift Container Platform")
    #endDef

    def configWKCSCC(self, icpdInstallLogFile):
        methodName = "configWKCSCC"
        TR.info(methodName,"  Start configuring WKC SCC")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        config_wkc_scc_command  = "./config_wkc_scc.sh " + self.cpd_instance_namespace

        TR.info(methodName,"Setting config WKC SCC with command %s"%config_wkc_scc_command)
        try:
            retcode = check_output(['bash','-c', config_wkc_scc_command]) 
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        TR.info(methodName,"Config WKC SCC with command %s returned %s"%(config_wkc_scc_command,retcode))
        
        time.sleep(60)

        TR.info(methodName,"  Completed WKC SCC")
    #endDef

    def updateTemplateFile(self, source, placeHolder, value):
        """
        method to update placeholder values in templates
        """
        source_content = open(source).read()
        updated_source_content = source_content.replace(placeHolder, value)
        updated_file = open(source, 'w')
        updated_file.write(updated_source_content)
        updated_file.close()
    #endDef    
    def readFileContent(self,source):
        file = open(source,mode='r')
        content = file.read()
        file.close()
        return content.rstrip()
   
    
    def _loadConf(self):
        methodName = "loadConf"
        TR.info(methodName,"Start load installation configuration")
        config = configparser.ConfigParser()
        config.read('../cpd_install.conf')

        self.ocp_admin_user = config['ocp_cred']['ocp_admin_user'].strip()
        self.ocp_admin_password = config['ocp_cred']['ocp_admin_password'].strip()
        self.image_registry_url = config['image_registry']['image_registry_url'].strip()
        self.image_registry_user = config['image_registry']['image_registry_user'].strip()
        self.image_registry_password = config['image_registry']['image_registry_password'].strip()
        self.change_node_settings = config['settings']['change_node_settings'].strip()
        self.config_image_pull = config['settings']['config_image_pull'].strip()
        self.overall_log_file = config['cpd_assembly']['overall_log_file'].strip()
        self.installWKC = config['cpd_assembly']['installWKC'].strip()
        self.installDb2U = config['cpd_assembly']['installDb2U'].strip()
        self.cpd_instance_namespace = config['cpd_assembly']['cpd_instance_namespace'].strip()
        TR.info(methodName,"Load installation configuration completed")
        TR.info(methodName,"Installation configuration:" + self.ocp_admin_user + "-" + self.ocp_admin_password  + "-" + self.installer_path)      
        TR.info("debug","image_registry_url= %s" %self.image_registry_url)
        TR.info("debug","image_registry_user= %s" %self.image_registry_user)
        TR.info("debug","image_registry_password= %s" %self.image_registry_password)
        TR.info("debug","cpd_instance_namespace= %s" %self.cpd_instance_namespace)
        TR.info("debug","installWKC= %s" %self.installWKC)
        TR.info("debug","installDb2U= %s" %self.installDb2U)
    #endDef

    def main(self,argv):
        methodName = "main"
        self.rc = 0

        try:
            beginTime = Utilities.currentTimeMillis()
           
            self._loadConf()   
      
            if (self.overall_log_file):
               self.overall_log_file = self.logsHome + "/" + self.overall_log_file
               #isExist = os.path.exists(self.overall_log_file)
               #if not isExist:
               #   os.makedirs(self.overall_log_file)
               TR.appendTraceLog(self.overall_log_file)   

            logFilePath = os.path.join(self.logsHome,"stdout.log")

            with open(logFilePath,"a+") as icpdInstallLogFile:  
                ocpstart = Utilities.currentTimeMillis()
                TR.info("debug","change_node_settings= %s" %self.change_node_settings)
                if(self.change_node_settings == "True"):
                    self.changeNodeSettings(icpdInstallLogFile)
                    TR.info("debug","Finishd the node settings")
                    ocpend = Utilities.currentTimeMillis()
                    self.printTime(ocpstart, ocpend, "Chaning node settings")
                
                TR.info("debug","config_image_pull= %s" %self.config_image_pull)
                
                ocpstart = Utilities.currentTimeMillis()
                if(self.config_image_pull == "True"):
                    self.configImagePull(icpdInstallLogFile)
                    TR.info("debug","Finishd the image pull configuration")
                    ocpend = Utilities.currentTimeMillis()
                    self.printTime(ocpstart, ocpend, "Configuring image pull")
                ocpstart = Utilities.currentTimeMillis()
                
                if(self.installDb2U == "True"):
                    self.configDb2Kubelet(icpdInstallLogFile)
                    TR.info("debug","Finishd the config of Db2 Kubelete")
                    ocpend = Utilities.currentTimeMillis()
                    self.printTime(ocpstart, ocpend, "Configuring Db2 Kubelete")

                if(self.installWKC == "True"):
                    self.configWKCSCC(icpdInstallLogFile)
                    TR.info("debug","Finishd the config of WKC SCC")
                    ocpend = Utilities.currentTimeMillis()
                    self.printTime(ocpstart, ocpend, "Configuring WKC SCC")
                
                self.installStatus = "CPD node settings and configuration completed"
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
            status = 'FAILURE: Check logs on the Boot node in cpd_install_accelerator.log'
            TR.info(methodName,"FAILED END CPD Quickstart.  Elapsed time (hh:mm:ss): %d:%02d:%02d" % (eth,etm,ets))
        #endIf                                            
    #end Def    
#endClass
if __name__ == '__main__':
  mainInstance = CPDInstall()
  mainInstance.main(sys.argv)
#endIf

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
        """

        methodName = "installCPD"

        #private_registry = self.image_registry_url
        offline_installation_dir = self.offline_dir_path

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        #Install Cloud Pak Foundation Service
        if(self.installFoundationalService == "True"):
            TR.info(methodName,"Start installing Foundational Service")
            
            bedrock_start = Utilities.currentTimeMillis()
            
            install_foundational_service_command  = "./install_bedrock.sh " + offline_installation_dir + " " + self.FoundationalService_Case_Name  + " " + self.image_registry_url + " " + self.foundation_service_namespace

            TR.info(methodName,"Install Foundational Service with command %s"%install_foundational_service_command)
            
            try:
                install_foundational_service_retcode = check_output(['bash','-c', install_foundational_service_command]) 
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
                return
            TR.info(methodName,"Install Foundational Service with command %s returned %s"%(install_foundational_service_command,install_foundational_service_retcode))
            
            bedrock_end = Utilities.currentTimeMillis()
            TR.info(methodName,"Install Foundational Service completed")
            self.printTime(bedrock_start, bedrock_end, "Install Foundational Service")   
        
        #Install Cloud Pak for Data Control Plane
        if(self.installCPDControlPlane == "True"):
            TR.info(methodName,"Start installing Cloud Pak for Data Control Plane (Zen)") 

            zen_core_metadb_storage_class = self.storage_class
            
            if(self.storage_type == "ocs"):
                zen_core_metadb_storage_class = "ocs-storagecluster-ceph-rbd" 

            zen_start = Utilities.currentTimeMillis()
            
            install_control_plane_command  = "./install_zen.sh " + offline_installation_dir + " " + self.CPDControlPlane_Case_Name  + " " + self.image_registry_url + " " + self.foundation_service_namespace + " " + self.cpd_operator_namespace + " " + self.cpd_instance_namespace + " " + self.cpd_license + " " + self.storage_class + " " + self.storage_type

            TR.info(methodName,"Install Control Plane with command %s"%install_control_plane_command)
            
            try:
                install_control_plane_retcode = check_output(['bash','-c', install_control_plane_command]) 
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
                return
            TR.info(methodName,"Install Control Plane with command %s returned %s"%(install_control_plane_command,install_control_plane_retcode))
            
            zen_end = Utilities.currentTimeMillis()
            TR.info(methodName,"Install Control Plane completed")
            self.printTime(zen_start, zen_end, "Install Control Plane")   

            get_cpd_route_cmd = "oc get route -n "+self.cpd_instance_namespace+ " | grep '"+self.cpd_instance_namespace+"' | awk '{print $2}'"
            TR.info(methodName, "Get CPD URL")
            try:
                self.cpdURL = check_output(['bash','-c', get_cpd_route_cmd]) 
                TR.info(methodName, "CPD URL retrieved %s"%self.cpdURL)
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))
                return   

        if(self.installWSL == "True"):
            TR.info(methodName,"Start installing Watson Studio Local") 

            wsl_start = Utilities.currentTimeMillis()
            
            install_wsl_command  = "./install_wsl.sh " + offline_installation_dir + " " + self.WSL_Case_Name  + " " + self.image_registry_url + " " + self.cpd_operator_namespace + " " + self.cpd_instance_namespace + " " + self.cpd_license + " " + self.storage_type + " " + self.storage_class

            TR.info(methodName,"Install Watson Studio with command %s"%install_wsl_command)
            
            try:
                install_wsl_retcode = check_output(['bash','-c', install_wsl_command]) 
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
            
            TR.info(methodName,"Install Watson Studio with command %s returned %s"%(install_wsl_command,install_wsl_retcode))
            
            wsl_end = Utilities.currentTimeMillis()
            TR.info(methodName,"Install Watson Studio completed")
            self.printTime(wsl_start, wsl_end, "Install Watson Studio")
        
        if(self.installWML == "True"):
            TR.info(methodName,"Start installing Watson Machine Learning") 
            wml_start = Utilities.currentTimeMillis()
            self.installCCSCatSrc(icpdInstallLogFile)
            
            install_wml_command  = "./install_wml.sh " + offline_installation_dir + " " + self.WML_Case_Name  + " " + self.image_registry_url + " " + self.cpd_operator_namespace + " " + self.cpd_instance_namespace + " " + self.cpd_license + " " + self.storage_type + " " + self.storage_class

            TR.info(methodName,"Install Watson Machine Learning with command %s"%install_wml_command)
            
            try:
                install_wml_retcode = check_output(['bash','-c', install_wml_command]) 
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
            
            TR.info(methodName,"Install Watson Machine Learning with command %s returned %s"%(install_wml_command,install_wml_retcode))
            
            wml_end = Utilities.currentTimeMillis()
            TR.info(methodName,"Install Watson Machine Learning completed")
            self.printTime(wml_start, wml_end, "Install Watson Machine Learning")

        if(self.installOSWML == "True"):
            TR.info(methodName,"Start installing Watson OpenScale") 
            wos_start = Utilities.currentTimeMillis()
            
            install_wos_command  = "./install_aiopenscale.sh " + offline_installation_dir + " " + self.WOS_Case_Name  + " " + self.image_registry_url + " " + self.cpd_operator_namespace + " " + self.cpd_instance_namespace + " " + self.cpd_license + " " + self.storage_type + " " + self.storage_class

            TR.info(methodName,"Install Watson OpenScale with command %s"%install_wos_command)
            
            try:
                install_wos_retcode = check_output(['bash','-c', install_wos_command]) 
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
            
            TR.info(methodName,"Install Watson OpenScale with command %s returned %s"%(install_wos_command,install_wos_retcode))
            
            wos_end = Utilities.currentTimeMillis()
            TR.info(methodName,"Install Watson OpenScale completed")
            self.printTime(wos_start, wos_end, "Install Watson OpenScale")  

        if(self.installCDE == "True"):
            TR.info(methodName,"Start installing Cognos Dashboards") 
            cde_start = Utilities.currentTimeMillis()
            self.installCCSCatSrc(icpdInstallLogFile)
            
            install_cde_command  = "./install_cde.sh " + offline_installation_dir + " " + self.CDE_Case_Name  + " " + self.image_registry_url + " " + self.cpd_operator_namespace + " " + self.cpd_instance_namespace + " " + self.cpd_license + " " + self.storage_type + " " + self.storage_class

            TR.info(methodName,"Install Cognos Dashboards with command %s"%install_cde_command)
            
            try:
                install_cde_retcode = check_output(['bash','-c', install_cde_command]) 
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
            
            TR.info(methodName,"Install Cognos Dashboards with command %s returned %s"%(install_cde_command,install_cde_retcode))
            
            cde_end = Utilities.currentTimeMillis()
            TR.info(methodName,"Install Cognos Dashboards completed")
            self.printTime(cde_start, cde_end, "Install Cognos Dashboards")

        
        if(self.installRStudio == "True"):
            TR.info(methodName,"Start installing RStudio package")
            rstudiostart = Utilities.currentTimeMillis()
            if(self.installRStudio_load_from == "NA"):
                self.installAssembliesAirgap("rstudio",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("rstudio",self.installRStudio_load_from,icpdInstallLogFile)
            rstudioend = Utilities.currentTimeMillis()
            TR.info(methodName,"RStudio package installation completed")
            self.printTime(rstudiostart, rstudioend, "Installing RStudio")      
        
        if(self.installSPSS == "True"):
            TR.info(methodName,"Start installing SPSS package")
            spssstart = Utilities.currentTimeMillis()
            if(self.installSPSS_load_from == "NA"):
                self.installAssembliesAirgap("spss-modeler",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("spss-modeler",self.installSPSS_load_from,icpdInstallLogFile)
            spssend = Utilities.currentTimeMillis()
            TR.info(methodName,"SPSS package installation completed")
            self.printTime(spssstart, spssend, "Installing SPSS")

        if(self.installSpark == "True"):
            TR.info(methodName,"Start installing Spark AE package")
            sparkstart = Utilities.currentTimeMillis()
            if(self.installSpark_load_from == "NA"):
                self.installAssembliesAirgap("spark",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("spark",self.installSpark_load_from,icpdInstallLogFile)
            sparkend = Utilities.currentTimeMillis()
            TR.info(methodName,"Spark AE  package installation completed")
            self.printTime(sparkstart, sparkend, "Installing Spark AE")     

        if(self.installRuntimeGPUPy37 == "True"):
            TR.info(methodName,"Start installing GPUPy37 package")
            gpupy36start = Utilities.currentTimeMillis()
            if(self.installRuntimeGPUPy37_load_from == "NA"):
                self.installAssembliesAirgap("runtime-addon-py37gpu",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("runtime-addon-py37gpu",self.installRuntimeGPUPy37_load_from,icpdInstallLogFile)
            gpupy36end = Utilities.currentTimeMillis()
            TR.info(methodName,"GPUPy36 package installation completed")
            self.printTime(gpupy36start, gpupy36end, "Installing GPUPy36")
        
        if(self.installDb2WH == "True"):
            TR.info(methodName,"Start installing Db2WH") 
            self.installDb2UOperator(icpdInstallLogFile)
            db2wh_start = Utilities.currentTimeMillis()
            
            install_db2wh_command  = "./install_db2wh.sh " + offline_installation_dir + " " + self.Db2WH_Case_Name  + " " + self.image_registry_url + " " + self.foundation_service_namespace + " " + self.cpd_operator_namespace + " " + self.cpd_instance_namespace + " " + self.cpd_license + " " + self.storage_type + " " + self.storage_class

            TR.info(methodName,"Install Db2WH with command %s"%install_db2wh_command)
            
            try:
                install_db2wh_retcode = check_output(['bash','-c', install_db2wh_command]) 
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
            
            TR.info(methodName,"Install Db2WH with command %s returned %s"%(install_db2wh_command,install_db2wh_retcode))
            
            db2wh_end = Utilities.currentTimeMillis()
            TR.info(methodName,"Install Db2WH completed")
            self.printTime(db2wh_start, db2wh_end, "Install Db2WH")  
        
        if(self.installHEE == "True"):
            TR.info(methodName,"Start installing HEE package")
            heestart = Utilities.currentTimeMillis()
            if(self.installHEE_load_from == "NA"):
                self.installAssembliesAirgap("hadoop-addon",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("hadoop-addon",self.installHEE_load_from,icpdInstallLogFile)
            heeend = Utilities.currentTimeMillis()
            TR.info(methodName,"HEE package installation completed")
            self.printTime(heestart, heeend, "Installing HEE")
        
        if(self.installDODS == "True"):
            TR.info(methodName,"Start installing DODS package")
            dodsstart = Utilities.currentTimeMillis()
            if(self.installDODS_load_from == "NA"):
                self.installAssembliesAirgap("dods",self.default_load_from,icpdInstallLogFile)
            else:
                self.installAssembliesAirgap("dods",self.installDODS_load_from,icpdInstallLogFile)
            dodsend = Utilities.currentTimeMillis()
            TR.info(methodName,"DODS package installation completed")
            self.printTime(dodsstart, dodsend, "Installing DODS") 

        if(self.installWKC == "True"):

            self.installDb2UOperator(icpdInstallLogFile)
            
            TR.info(methodName,"Start installing Watson Knowledge Catalog") 

            wkcstart = Utilities.currentTimeMillis()
            
            install_wkc_command  = "./install_wkc.sh " + offline_installation_dir + " " + self.WKC_Case_Name  + " " + self.image_registry_url + " " + self.foundation_service_namespace + " " + self.cpd_operator_namespace + " " + self.cpd_instance_namespace + " " + self.cpd_license + " " + self.storage_type + " " + self.storage_class
            TR.info(methodName,"Install Watson Knowledge Catalog with command %s"%install_wkc_command)
            
            install_wkc_retcode = ""
            try:
                install_wkc_retcode = check_output(['bash','-c', install_wkc_command]) 
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
            
            TR.info(methodName,"Install Watson Knowledge Catalog with command %s returned %s"%(install_wkc_command,install_wkc_retcode))
            
            wkcend = Utilities.currentTimeMillis()
            TR.info(methodName,"Install Watson Knowledge Catalog completed")
            self.printTime(wkcstart, wkcend, "Install Watson Knowledge Catalog")
            
        if(self.installDV == "True"):

            self.installDb2UOperator(icpdInstallLogFile)
            
            TR.info(methodName,"Start installing Data Virtualization") 

            dvstart = Utilities.currentTimeMillis()
            
            install_dv_command  = "./install_dv.sh " + offline_installation_dir + " " + self.DV_Case_Name  + " " + self.image_registry_url + " " + self.foundation_service_namespace + " " + self.cpd_operator_namespace + " " + self.cpd_instance_namespace + " " + self.cpd_license
            TR.info(methodName,"Install Data Virtualization with command %s"%install_dv_command)
            
            install_dv_retcode = ""
            try:
                install_dv_retcode = check_output(['bash','-c', install_dv_command]) 
            except CalledProcessError as e:
                TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
            
            TR.info(methodName,"Install Data Virtualization with command %s returned %s"%(install_dv_command,install_dv_retcode))
            
            dvend = Utilities.currentTimeMillis()
            TR.info(methodName,"Install Data Virtualization completed")
            self.printTime(dvstart, dvend, "Install Data Virtualization")    


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

        TR.info(methodName,"  Completed node settings of Openshift Container Platform")
    #endDef

    def configImagePull(self, icpdInstallLogFile):
        ##setup-global-pull-secret-bedrock.sh
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

        #time.sleep(900)

        TR.info(methodName,"  Completed image pull related setting")
    #endDef
    def installCCSCatSrc(self, icpdInstallLogFile):
       
        methodName = "installCCSCatSrc"
        TR.info(methodName," Start installing CCS catalog source")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        install_ccs_command  = "./install_ccs.sh " + self.offline_dir_path + " " + self.CCS_Case_Name 

        TR.info(methodName,"Installing CCS catalog source with command %s"%install_ccs_command)
        try:
            retcode = check_output(['bash','-c', install_ccs_command]) 
            TR.info(methodName,"Installing CCS catalog source with command %s returned %s"%(install_ccs_command,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        time.sleep(60)

        TR.info(methodName,"  Completed CCS catalog source installation")
    #endDef

    def installDb2UOperator(self, icpdInstallLogFile):
       
        methodName = "installDb2UOperator"
        TR.info(methodName," Start installing Db2U operator")  

        self.logincmd = "oc login -u " + self.ocp_admin_user + " -p "+self.ocp_admin_password
        try:
            call(self.logincmd, shell=True,stdout=icpdInstallLogFile)
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        TR.info(methodName,"oc login successfully")

        install_db2u_command  = "./install_db2u.sh " + self.offline_dir_path + " " + self.Db2aas_Case_Name + " " + self.Db2U_Case_Name + " " + self.cpd_operator_namespace 
        #install_db2u_command  = "./install_db2u.sh " + self.offline_dir_path + " " + self.Db2U_Case_Name + " " + "ibm-db2aaservice-4.0.3.tgz"

        TR.info(methodName,"Installing Db2U with command %s"%install_db2u_command)
        try:
            retcode = check_output(['bash','-c', install_db2u_command]) 
            TR.info(methodName,"Installing Db2U with command %s returned %s"%(install_db2u_command,retcode))
        except CalledProcessError as e:
            TR.error(methodName,"command '{}' return with error (code {}): {}".format(e.cmd, e.returncode, e.output))    
        
        time.sleep(60)

        TR.info(methodName,"  Completed Db2U catalog source installation")
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
        self.log_dir = config['cpd_assembly']['log_dir'].strip()
        self.overall_log_file = config['cpd_assembly']['overall_log_file'].strip()
        self.offline_dir_path = config['cpd_assembly']['offline_dir_path'].strip()
        self.installer_path = config['cpd_assembly']['installer_path'].strip()
        self.installFoundationalService = config['cpd_assembly']['installFoundationalService'].strip()
        self.FoundationalService_Case_Name = config['cpd_assembly']['FoundationalService_Case_Name'].strip()
        self.installCPDControlPlane = config['cpd_assembly']['installCPDControlPlane'].strip()
        self.CPDControlPlane_Case_Name = config['cpd_assembly']['CPDControlPlane_Case_Name'].strip()
        self.installWSL = config['cpd_assembly']['installWSL'].strip()
        self.WSL_Case_Name = config['cpd_assembly']['WSL_Case_Name'].strip()
        self.installCCS = config['cpd_assembly']['installCCS'].strip()
        self.CCS_Case_Name = config['cpd_assembly']['CCS_Case_Name'].strip()
        self.installWML = config['cpd_assembly']['installWML'].strip()
        self.WML_Case_Name = config['cpd_assembly']['WML_Case_Name'].strip()
        self.installDb2U = config['cpd_assembly']['installDb2U'].strip()
        self.Db2U_Case_Name = config['cpd_assembly']['Db2U_Case_Name'].strip()
        self.Db2aas_Case_Name = config['cpd_assembly']['Db2aas_Case_Name'].strip()
        self.installWKC = config['cpd_assembly']['installWKC'].strip()
        self.WKC_Case_Name = config['cpd_assembly']['WKC_Case_Name'].strip()
        self.installSpark = config['cpd_assembly']['installSpark'].strip()
        self.installCDE = config['cpd_assembly']['installCDE'].strip()
        self.CDE_Case_Name = config['cpd_assembly']['CDE_Case_Name'].strip()
        self.installDMC = config['cpd_assembly']['installDMC'].strip()
        self.DMC_Case_Name = config['cpd_assembly']['DMC_Case_Name'].strip()
        self.installDV = config['cpd_assembly']['installDV'].strip()
        self.DV_Case_Name = config['cpd_assembly']['DV_Case_Name'].strip()
        self.installOSWML = config['cpd_assembly']['installOSWML'].strip()
        self.WOS_Case_Name = config['cpd_assembly']['WOS_Case_Name'].strip()
        self.installRStudio = config['cpd_assembly']['installRStudio'].strip()
        self.installSPSS = config['cpd_assembly']['installSPSS'].strip()       
        self.installRuntimeGPUPy37 = config['cpd_assembly']['installRuntimeGPUPy37'].strip()
        self.installDb2WH = config['cpd_assembly']['installDb2WH'].strip()
        self.Db2WH_Case_Name = config['cpd_assembly']['Db2WH_Case_Name'].strip()
        self.installHEE = config['cpd_assembly']['installHEE'].strip()
        self.installDODS = config['cpd_assembly']['installDODS'].strip()
        self.storage_type = config['cpd_assembly']['storage_type'].strip()    
        self.storage_class = config['cpd_assembly']['storage_class'].strip()        
        self.foundation_service_namespace = config['cpd_assembly']['foundation_service_namespace'].strip()
        self.cpd_operator_namespace = config['cpd_assembly']['cpd_operator_namespace'].strip()
        self.cpd_instance_namespace = config['cpd_assembly']['cpd_instance_namespace'].strip()
        self.cpd_license = config['cpd_assembly']['cpd_license'].strip()
        TR.info(methodName,"Load installation configuration completed")
        TR.info(methodName,"Installation configuration:" + self.ocp_admin_user + "-" + self.ocp_admin_password  + "-" + self.installer_path)      
        TR.info("debug","image_registry_url= %s" %self.image_registry_url)
        TR.info("debug","image_registry_user= %s" %self.image_registry_user)
        TR.info("debug","image_registry_password= %s" %self.image_registry_password)
        TR.info("debug","foundation_service_namespace= %s" %self.foundation_service_namespace)
        TR.info("debug","cpd_operator_namespace= %s" %self.cpd_operator_namespace)
        TR.info("debug","cpd_instance_namespace= %s" %self.cpd_instance_namespace)
        TR.info("debug","installFoundationalService= %s" %self.installFoundationalService)
        TR.info("debug","FoundationalService_Case_Name= %s" %self.FoundationalService_Case_Name)
        TR.info("debug","installCPDControlPlane= %s" %self.installCPDControlPlane)
        TR.info("debug","CPDControlPlane_Case_Name= %s" %self.CPDControlPlane_Case_Name)             
        TR.info("debug","installWSL= %s" %self.installWSL)
        TR.info("debug","WSL_Case_Name= %s" %self.WSL_Case_Name) 
        TR.info("debug","installCCS= %s" %self.installCCS)
        TR.info("debug","CCS_Case_Name= %s" %self.CCS_Case_Name) 
        TR.info("debug","installWML= %s" %self.installWML)
        TR.info("debug","WML_Case_Name= %s" %self.WML_Case_Name) 
        TR.info("debug","installDb2U= %s" %self.installDb2U)
        TR.info("debug","Db2aas_Case_Name= %s" %self.Db2aas_Case_Name)
        TR.info("debug","Db2U_Case_Name= %s" %self.Db2U_Case_Name) 
        TR.info("debug","installWKC= %s" %self.installWKC)
        TR.info("debug","WKC_Case_Name= %s" %self.WKC_Case_Name)
        TR.info("debug","installDV= %s" %self.installDV)
        TR.info("debug","DV_Case_Name= %s" %self.DV_Case_Name)
        TR.info("debug","installDMC= %s" %self.installDMC)
        TR.info("debug","DMC_Case_Name= %s" %self.DMC_Case_Name)
        TR.info("debug","installOSWML= %s" %self.installOSWML)
        TR.info("debug","WOS_Case_Name= %s" %self.WOS_Case_Name) 
        TR.info("debug","installCDE= %s" %self.installCDE)
        TR.info("debug","CDE_Case_Name= %s" %self.CDE_Case_Name) 
        TR.info("debug","installSpark= %s" %self.installSpark)
        TR.info("debug","installRStudio= %s" %self.installRStudio)
        TR.info("debug","installSPSS= %s" %self.installSPSS)
        TR.info("debug","installRuntimeGPUPy37= %s" %self.installRuntimeGPUPy37)
        TR.info("debug","installDb2WH= %s" %self.installDb2WH)
        TR.info("debug","Db2WH_Case_Name= %s" %self.Db2WH_Case_Name)  
        TR.info("debug","installHEE= %s" %self.installHEE)
        TR.info("debug","installDODS= %s" %self.installDODS) 
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

                if(self.installOSWML == "True"):
                    self.installWML="True" 

                self.installCPD(icpdInstallLogFile)
                
                self.installStatus = "CPD Installation completed"
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

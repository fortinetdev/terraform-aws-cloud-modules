## Overview

The example name is based on the traffic path from the user's VM on spoke VPC to the internet. For instance, spk_tgw_gwlb_asg_fgt_gwlb_igw means traffic path will be Spoke_VPC --> Transit Gateway --> Gateway Load Balancer --> FortiGate instance of Auto-scaling Group --> Internet Gateway.

## Pre-requirement:

| Ecosystem | Version |
|-----------|---------|
| [terraform](https://www.terraform.io) | >= 1.3 |

## How to play
There are two ways to use the example.
#### Copy example:

Directly copy the folder or files to the test location. In this way, user could have more flexibility to modify the example.

Steps:

* Create a folder for the test. 
* Copy all files under examples/&lt;EXAMPLE NAME&gt; to the new folder.
* Change the name of file terraform.tfvars.txt to terraform.tfvars. 
* Modify and check the arguments in file terraform.tfvars.
* Run 'terraform init' to initiate it.
* Run 'terraform plan' to check whether the output is expected.
* Run 'terraform apply' to apply it. It may take several minutes to complete it.

#### Use example as module (Only recommend for the test, since examples name or features may change):

Using the example as a module. In this way, user just needs to care about the configurations.

Steps:

* Create a folder for the test.
* Create a .tf file with the configurations inside the module block. You could directly copy the file content of file terraform.tfvars to the module block.
* Modify and check the arguments.
* Run 'terraform init' to initiate it.
* Run 'terraform plan' to check whether the output is expected.
* Run 'terraform apply' to apply it. It may take several minutes to complete it.

## Note for the configuration:

* For the CIDR block of the VPC, currently we do not support a netmask larger than 24 for the auto-generate subnets. If the netmask of the CIDR block is larger than 24, please manually provide the argument `subnets` to identify subnet information for each subnet. 
* The key pair should be created by user manually.
* FortiGate instance password is required due to the lambda function. The module will change the password of FortiGate instance to the given value.
* License is required when the argument 'license_type' is set to 'byol'. Otherwise, user needs to manually check the instance launching status and upload the license manually. Also, the module could not configure the FortiGate settings without a license. There are two ways to provide licenses. Please see 'License' section below.
* The module will do basic interface configuration for the FortiGate instance based on the interface settings. For other configurations, like firewall policy and routers, users need to provide the configuration by one of the following options:

    * `user_conf_content` : FortiGate Configuration content in CLI format;
    * `user_conf_file_path` : The file path of the configuration file;
    * `user_conf_s3` : Map of AWS S3;

## License

We provide two options for the license. One is using license files, and another is using FortiFlex.

#### License file

The lambda function will auto-apply the available license file to the launched FortiGate instance.The function will also track the license files. The license file will go back to the available list and be ready to use for the next FortiGate instance when a FortiGate instance is terminated. We have two options to provide the license files:
1. Variable `lic_folder_path`
Provide the folder path of the local directory. The example will create an S3 bucket and upload license files in this directory to the S3 bucket. 
2. Variable `lic_s3_name`
Provide the S3 bucket name that contains license files.

#### FortiFlex
    
The user needs to provide a refresh token of FortiCloud account by the variable `fortiflex_refresh_token`. How to get a refresh token: [FNDN](https://fndn.fortinet.net/index.php?/fortiapi/954-fortiflex/956/) or [Fortinet Document](https://docs.fortinet.com/document/fortiauthenticator/latest/rest-api-solution-guide/498666/oauth-server-token-oauth-token). Note: We need the refresh_token, not access_token.

Also, the user needs to provide one or more of the following variables:
1. Variable `fortiflex_sn_list`

    Provide a list of valid Serial numbers from the FortiFlex account. The lambda function will generate the VM token and apply it to the newly launched FortiGate instance automatically. The function will also track the serial numbers. The serial number will go back to the available list and be ready to use for the next FortiGate instance when a FortiGate instance is terminated.  

2. Variable `fortiflex_configid_list`

    Provide a list of config IDs from the FortiFlex account. The lambda function will get all valid serial numbers of the given config IDs. The function will refresh the serial numbers on each event (launch or terminate instance).
## Unreleased

## 1.1.1 (Apr 28, 2025)

IMPROVEMENTS:
* Support UMS features by adding FortiManager infomation on the boot config of FortiGate instance;
* Support primary instance scale-in protection; 
* Improve lambda function to check and clean up the terminated instances that did not trigger the terminate event;
* Adjust user config position on Lambda function to avoid reboot;
* Add variable fgt_config_shared to support shared FortiGate configuration for all ASGs on variable asgs on each example;
* Update document;

## 1.1.0 (Nov 25, 2024)

IMPROVEMENTS:
* Add module fgt;
* Add example fgt_standalone;
* Support option of not assign public IP for all FortiGate instance;
* Support create extra interfaces for FortiGate instance;
* Add output of 'gwlb_endps' to output the GWLB's endpoints information on all examples;
* Support creating GWLB endpoints under spoke vpc for example spk_tgw_gwlb_asg_fgt_igw;

## 1.0.3 (Oct 4, 2024)

IMPROVEMENTS:

* Support private link for DynamoDB by VPC endpoint; 
* Add module prefix to avoid conflict when apply multiple times;
* Avoid using Fortiflex token with ACTIVE status and already used;

## 1.0.2 (Apr 9, 2024)

IMPROVEMENTS:

* Fix issue of get federal image of FOS; 
* Update upload fortiflex token to make the token in the data field; 
* Update doc of example spk_gwlb_asg_fgt_wlb_igw; 
* Add variable ami_id to support user providing FOS AMI ID;

## 1.0.1 (Dec 20, 2023)

IMPROVEMENTS:

* Support FortiFlex API username/password;
* Support using existing resources;
* Fix issue of FortiFlex SN not stoped after instance been terminated;
* Fix validation check error of variable 'security_vpc_tgw_attachments';

## 1.0.0 (Oct 20, 2023)

* Initial release

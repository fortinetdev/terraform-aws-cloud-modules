## Terraform modules for Fortinet VM products on AWS

Terraform modules for deploying Fortinet VM products (e.g. FortiGate VM) on AWS. 

Folder `modules` contains reusable modules for AWS configurations (Subfolder `aws`) and Fortinet VM products (Other subfolders). 

Folder `examples` contains examples for certain structures of security solutions. Please Note: Templates under folder `examples` are examples which the name or content may change. Directly reference a examples as module are not recommended.

## Supported features of examples

1. Multi-ASGs:
    
    All examples support multiple Auto Scaling Groups by configuring variable `asgs`. Example configuration of file `terraform.tfvars.txt` on each module is hybrid licensing module.

2. Support using existing resources:

    All examples support using existing resources. Check variables with prefix `existing_` on variable.tf.

3. Support FortiFlex for licensing:

    [FortiFlex](https://www.fortinet.com/products/fortiflex) delivers flexible, simple on-demand licensing and provisioning for security solutions and services for all environments. 

## Image version update

FortiGate image version could be updated by the variable `fgt_version` under the variable `asgs` for each ASG examples. The rule is to get the latest version of the FortiGate on AWS. For instance, if fgt_version is set to ‘7.4.5’, the module will get the FortiGate image of 7.4.5; if fgt_version is set to ‘7.4’, then the module will get the latest version of ‘7.4’, like it will get ‘7.4.6’ if the current latest version is ‘7.4.6’; if fgt_version is set to ‘7’, then the module will get the latest version of ‘7’, like it will get ‘7.6.2’ if the current latest version is ‘7.6.2’.

> [!NOTE] 
> If update the fgt_version after deployed, the updated version will only apply to the new launched instances after the update. Existing instances will not been updated, since the module will update the template of the ASG.


## Request, Question or Issue

If there is a missing feature or a bug - - [open an issue](https://github.com/fortinetdev/terraform-aws-cloud-modules/issues/new)

## License

[License](./LICENSE) © Fortinet Technologies. All rights reserved.
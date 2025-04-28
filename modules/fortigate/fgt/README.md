## Module fgt

This module is used to create a single FortiGate instance on AWS.

## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.3, < 2.0.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_eip.fgt_eips](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eip) | resource |
| [aws_eip_association.fgt](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eip_association) | resource |
| [aws_instance.fgt](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance) | resource |
| [aws_network_interface.fgt_intfs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/network_interface) | resource |
| [aws_network_interface_attachment.fgt](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/network_interface_attachment) | resource |
| [aws_ami.fgt_ami](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_ami_id"></a> [ami\_id](#input\_ami\_id) | The AMI ID of FortiOS image. If you leave this blank, Terraform will get the AMI ID from AWS market place with the given FortiOS version. | `string` | `""` | no |
| <a name="input_availability_zone"></a> [availability\_zone](#input\_availability\_zone) | AZ to start the instance in. | `string` | `""` | no |
| <a name="input_cpu_options"></a> [cpu\_options](#input\_cpu\_options) | CPU options apply to the instance at launch time. | <pre>object({<br/>    amd_sev_snp = optional(string, "")<br/>    core_count = optional(string, "")<br/>    threads_per_core = optional(string, "")<br/>  })</pre> | `{}` | no |
| <a name="input_fgt_admin_https_port"></a> [fgt\_admin\_https\_port](#input\_fgt\_admin\_https\_port) | FortiGate instance HTTPS admin access port. | `string` | `""` | no |
| <a name="input_fgt_admin_ssh_port"></a> [fgt\_admin\_ssh\_port](#input\_fgt\_admin\_ssh\_port) | FortiGate instance SSH admin access port. | `string` | `""` | no |
| <a name="input_fgt_hostname"></a> [fgt\_hostname](#input\_fgt\_hostname) | FortiGate instance hostname. | `string` | `""` | no |
| <a name="input_fgt_multi_vdom"></a> [fgt\_multi\_vdom](#input\_fgt\_multi\_vdom) | Whether FortiGate instance enable multi-vdom mode. Default is false. Note: Only license\_type set to byol could enable multi-vdom mode. | `bool` | `false` | no |
| <a name="input_fgt_password"></a> [fgt\_password](#input\_fgt\_password) | FortiGate instance login password. If not set, the default password will be the instance ID. You need to change it at the first time login by GUI or CLI. | `string` | `""` | no |
| <a name="input_fgt_version"></a> [fgt\_version](#input\_fgt\_version) | Provide the FortiGate version for the FortiGate instances. If the whole version been provided, please make sure the version is exist. If part of version been provided, such as 7.2, will using the latest release of this version. Default is 7.2. | `string` | `"7.2"` | no |
| <a name="input_fortiflex_token"></a> [fortiflex\_token](#input\_fortiflex\_token) | FortiFlex token that used for BYOL type of FortiGate instance. | `string` | `""` | no |
| <a name="input_instance_name"></a> [instance\_name](#input\_instance\_name) | FortiGate instance name. | `string` | `""` | no |
| <a name="input_instance_type"></a> [instance\_type](#input\_instance\_type) | Provide the instance type for the FortiGate instances. | `string` | `"c5.xlarge"` | no |
| <a name="input_keypair_name"></a> [keypair\_name](#input\_keypair\_name) | The keypair name that used in FortiGate EC2 instance. | `string` | n/a | yes |
| <a name="input_lic_file_path"></a> [lic\_file\_path](#input\_lic\_file\_path) | FortiGate license file path that used for BYOL type of FortiGate instance. | `string` | `""` | no |
| <a name="input_license_type"></a> [license\_type](#input\_license\_type) | Provide the license type for the FortiGate instances. Options: on\_demand, byol. Default is on\_demand. | `string` | `"on_demand"` | no |
| <a name="input_module_prefix"></a> [module\_prefix](#input\_module\_prefix) | Prefix that will be used in the whole module. | `string` | `""` | no |
| <a name="input_network_interfaces"></a> [network\_interfaces](#input\_network\_interfaces) | Network interfaces configuration for FortiGate VM instance.<br/>Format:<pre>network_interfaces = {<br/>      \<Key\> = {<br/>          \<Option\> = \<Option value\><br/>      }<br/>  }</pre>Key:<br/>  Name of the interface.<br/><br/>Options:<br/>  - device\_index       : (Required\|int) Integer to define the network interface index. Interface with `0` will be attached at boot time.<br/>  - subnet\_id          : (Required\|string) Subnet ID to create the ENI in.<br/>  - vdom               : (Optional\|string) Vdom name that the interface belongs to. Only works when vdom mode is multi-vdom. Default will be root if not set and vdom mode is multi-vdom.<br/>  - description        : (Optional\|string) Description for the network interface.<br/>  - private\_ips        : (Optional\|list) List of private IPs to assign to the ENI without regard to order.<br/>  - source\_dest\_check  : (Optional\|bool) Whether to enable source destination checking for the ENI. Defaults false.<br/>  - security\_groups    : (Optional\|list) List of security group IDs to assign to the ENI. Defaults null.<br/>  - enable\_public\_ip   : (Optional\|bool) Whether to assign a public IP for the ENI. Defaults to false.<br/>  - public\_ipv4\_pool   : (Optional\|string) Specify EC2 IPv4 address pool. If not set, Amazon's poll will be used. Only useful when `enable_public_ip` is set to true.<br/>  - existing\_eip\_id    : (Optional\|string) Associate an existing EIP to the ENI. Sould set enable\_public\_ip to false.<br/><br/>Example:<pre>network_interfaces = {<br/>  mgmt = {<br/>    device_index       = 0<br/>    subnet_id          = \<SUBNET_ID\><br/>    enable_public_ip   = true<br/>    source_dest_check  = true<br/>    security_groups = ["\<SECURITY_GROUP_ID\>"]<br/>  },<br/>  public1 = {<br/>    device_index     = 1<br/>    subnet_id        = \<SUBNET_ID\><br/>    existing_eip_id  = \<ELISTIC_IP_ID\><br/>  }<br/>}</pre> | `any` | n/a | yes |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags that applies to related resources.<br/>Format:<pre>tags = {<br/>      \<Option\> = \<Option value\><br/>  }</pre>Options:<br/>  - general          :  Tags will add to all resources.<br/>  - instance         :  Tags for EC2 instance.<br/>  - interface        :  Tags for network interfaces.<br/>  - eip              :  Tags for Elistic IPs.<br/>  - eip\_association  :  Tags for Elistic IP Associations.<br/><br/>Example:<pre>tags = {<br/>  general = {<br/>    Created_from = "Terraform"<br/>  },<br/>  instance = {<br/>    Used_to = "ASG"<br/>  }<br/>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_user_conf"></a> [user\_conf](#input\_user\_conf) | User configuration in CLI format that will applied to the FortiGate instance. | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_fgt_instance"></a> [fgt\_instance](#output\_fgt\_instance) | n/a |
| <a name="output_fgt_interface_ids"></a> [fgt\_interface\_ids](#output\_fgt\_interface\_ids) | n/a |
| <a name="output_fgt_private_ips"></a> [fgt\_private\_ips](#output\_fgt\_private\_ips) | n/a |
| <a name="output_fgt_public_ip"></a> [fgt\_public\_ip](#output\_fgt\_public\_ip) | n/a |
| <a name="output_fgt_public_ips"></a> [fgt\_public\_ips](#output\_fgt\_public\_ips) | n/a |

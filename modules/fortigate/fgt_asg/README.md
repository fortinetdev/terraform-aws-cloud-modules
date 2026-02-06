## Module fgt_asg

This module is used to create a FortiGate Auto Scaling Group(ASG). 

## FortiGate licensing

This module supports two FortiGate licensing modes: Pay As You Go (PAYG) and Bring Your Own License (BYOL). When using a BYOL image, you must provide a license. The module supports both a license file and a FortiFlex token. If both are provided, the license file takes priority.

### License file

There are 2 variables related to license file:
* `lic_s3_name` The AWS S3 bucket name that contains FortiGate license files. 
* `lic_folder_path`: The local folder path that contains license files. 
The module will automatically create the specified S3 bucket (if it doesn't exist) and upload the license files from the local path.

### FortiFlex token

There are five variables associated with FortiFlex:

* `fortiflex_refresh_token`: The FortiFlex refresh token used for authentication. Refresh token could only be used for one deploy, you need to provide a new refresh token if you redeploy it or deploy another one.
* `fortiflex_username` and `fortiflex_password`: An alternative to the refresh token for authentication.
* `fortiflex_sn_list`: A list of specific FortiGate serial numbers to use.
* `fortiflex_configid_list`: A list of FortiFlex configuration IDs.

If `fortiflex_configid_list` is provided, the module's Lambda function will automatically retrieve all valid serial numbers under each configuration ID. Check [here](/docs/fortiflex.md) for creating FortiFlex credential.

### Lambda function workflow

![Lambda function workflow](/docs/images/Lambda_function_flow.png)## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.3, < 2.0.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_archive"></a> [archive](#provider\_archive) | n/a |
| <a name="provider_aws"></a> [aws](#provider\_aws) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_autoscaling_group.fgt-asg](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/autoscaling_group) | resource |
| [aws_autoscaling_policy.scale_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/autoscaling_policy) | resource |
| [aws_cloudwatch_event_rule.fgt_asg_launch](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule) | resource |
| [aws_cloudwatch_event_rule.fgt_asg_terminate](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule) | resource |
| [aws_cloudwatch_event_target.fgt_asg_launch](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target) | resource |
| [aws_cloudwatch_event_target.fgt_asg_terminate](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target) | resource |
| [aws_cloudwatch_log_group.fgt_asg_lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_cloudwatch_log_group.fgt_asg_lambda_internal](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_dynamodb_table.track_table](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table) | resource |
| [aws_dynamodb_table_item.user_config](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table_item) | resource |
| [aws_iam_role.iam_for_lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.iam_policy](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_lambda_function.fgt_asg_lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_lambda_function.fgt_asg_lambda_internal](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_lambda_layer_version.lambda_layer_requests](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_layer_version) | resource |
| [aws_lambda_permission.lambda_permission](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission) | resource |
| [aws_launch_template.fgt](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/launch_template) | resource |
| [aws_s3_bucket.fgt_lic](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket) | resource |
| [aws_s3_object.fgt_intf_track_file](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_object) | resource |
| [aws_s3_object.fgt_lic](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_object) | resource |
| [aws_s3_object.fgt_lic_track_file](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_object) | resource |
| [aws_security_group.lamnda_sg](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_security_group.sg_allow_lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_vpc_endpoint.dynamodb](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint) | resource |
| [archive_file.lambda_private](https://registry.terraform.io/providers/hashicorp/archive/latest/docs/data-sources/file) | data source |
| [archive_file.lambda_public](https://registry.terraform.io/providers/hashicorp/archive/latest/docs/data-sources/file) | data source |
| [aws_ami.fgt_ami](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami) | data source |
| [aws_iam_policy_document.assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_ami_id"></a> [ami\_id](#input\_ami\_id) | The AMI ID of FortiOS image. If you leave this blank, Terraform will get the AMI ID from AWS market place with the given FortiOS version. | `string` | `""` | no |
| <a name="input_asg_desired_capacity"></a> [asg\_desired\_capacity](#input\_asg\_desired\_capacity) | Number of Amazon EC2 instances that should be running in the group. | `number` | `null` | no |
| <a name="input_asg_gwlb_tgp"></a> [asg\_gwlb\_tgp](#input\_asg\_gwlb\_tgp) | Set of aws\_alb\_target\_group ARNs | `list(string)` | `[]` | no |
| <a name="input_asg_health_check_grace_period"></a> [asg\_health\_check\_grace\_period](#input\_asg\_health\_check\_grace\_period) | Time (in seconds) after instance comes into service before checking health. | `number` | `300` | no |
| <a name="input_asg_health_check_type"></a> [asg\_health\_check\_type](#input\_asg\_health\_check\_type) | 'EC2' or 'ELB'. Controls how health checking is done. | `string` | `""` | no |
| <a name="input_asg_max_size"></a> [asg\_max\_size](#input\_asg\_max\_size) | Maximum size of the Auto Scaling Group. | `number` | n/a | yes |
| <a name="input_asg_min_size"></a> [asg\_min\_size](#input\_asg\_min\_size) | Minimum size of the Auto Scaling Group. | `number` | n/a | yes |
| <a name="input_asg_name"></a> [asg\_name](#input\_asg\_name) | Name of the Auto Scaling Group. | `string` | n/a | yes |
| <a name="input_availability_zones"></a> [availability\_zones](#input\_availability\_zones) | List of one or more availability zones for the group. | `list(string)` | `[]` | no |
| <a name="input_az_name_map"></a> [az\_name\_map](#input\_az\_name\_map) | Name map for availability. | `map(string)` | `{}` | no |
| <a name="input_create_dynamodb_table"></a> [create\_dynamodb\_table](#input\_create\_dynamodb\_table) | If true, will create the DynamoDB table using dynamodb\_table\_name as the name. Default is false. | `bool` | `false` | no |
| <a name="input_create_geneve_for_all_az"></a> [create\_geneve\_for\_all\_az](#input\_create\_geneve\_for\_all\_az) | If true, FotiGate instance will create GENEVE turnnels for all availability zones. Set to true if Gateway Load Balancer enabled cross zone load balancing. | `bool` | `false` | no |
| <a name="input_dynamodb_privatelink"></a> [dynamodb\_privatelink](#input\_dynamodb\_privatelink) | DynamoDB private link by VPC endpoint.<br/>Options:<br/>  - vpc\_id                      : (Required\|string) VPC ID that will used to create interface endpoint.<br/>  - region                      : (Required\|string) The region to deploy the interface endpoint.<br/>  - privatelink\_subnet\_ids      : (Required\|list) Subnet ID list to create interface endpoint.<br/>  - privatelink\_security\_groups : (Required\|list) Security group ID list to create interface endpoint.<br/><br/>Example:<pre>scale_policies = {<br/>  vpc_id = \<VPC_id\> <br/>  region = "us-west-1"<br/>  privatelink_subnet_ids = ["\<subnet_id\>"]<br/>  privatelink_security_groups = ["\<security_group_name\>"]<br/>}</pre> | <pre>object({<br/>    vpc_id = string<br/>    region = string<br/>    privatelink_subnet_ids = list(string)<br/>    privatelink_security_groups = list(string)<br/>  })</pre> | `null` | no |
| <a name="input_dynamodb_table_name"></a> [dynamodb\_table\_name](#input\_dynamodb\_table\_name) | DynamoDB table name that used for tracking Auto Scale Group information, such as instance information and primary IP. | `string` | n/a | yes |
| <a name="input_enable_fgt_system_autoscale"></a> [enable\_fgt\_system\_autoscale](#input\_enable\_fgt\_system\_autoscale) | If true, FotiGate system auto-scale will be set. | `bool` | `false` | no |
| <a name="input_fgt_hostname"></a> [fgt\_hostname](#input\_fgt\_hostname) | FortiGate instance hostname. | `string` | `""` | no |
| <a name="input_fgt_login_port_number"></a> [fgt\_login\_port\_number](#input\_fgt\_login\_port\_number) | The port number for the FortiGate instance. Should set this parameter if the port number for FortiGate instance login is not 443. | `string` | `""` | no |
| <a name="input_fgt_multi_vdom"></a> [fgt\_multi\_vdom](#input\_fgt\_multi\_vdom) | Whether FortiGate instance enable multi-vdom mode. Default is false. Note: Only license\_type set to byol could enable multi-vdom mode. | `bool` | `false` | no |
| <a name="input_fgt_password"></a> [fgt\_password](#input\_fgt\_password) | FortiGate instance login password. This is required for BYOL type of FortiGate instance since we need to upload the license to the instance by lambda function. | `string` | n/a | yes |
| <a name="input_fgt_system_autoscale_psksecret"></a> [fgt\_system\_autoscale\_psksecret](#input\_fgt\_system\_autoscale\_psksecret) | FotiGate system auto-scale psksecret. | `string` | `""` | no |
| <a name="input_fgt_version"></a> [fgt\_version](#input\_fgt\_version) | Provide the FortiGate version for the FortiGate instances. If the whole version been provided, please make sure the version is exist. If part of version been provided, such as 7.2, will using the latest release of this version. Default is 7.2. | `string` | `"7.4"` | no |
| <a name="input_fmg_integration"></a> [fmg\_integration](#input\_fmg\_integration) | Register FortiGate instance to the FortiManager."<br/>Options:<br/>  - ip : (Required\|string) FortiManager public IP.<br/>  - sn : (Required\|string) FortiManager serial number.<br/>  - fgt\_lic\_mgmt : (Optional\|string) FortiGate license management type. Options: 'fmg', 'module'. 'fmg': License handled by the FortiManager, which the module will not perform license related operations. Default: fmg.<br/>  - vrf\_select : (Optional\|number) VRF ID used for connection to server. <br/>  - primary\_only : (Optional\|bool) Whether the FortiManager integration only apply to primary FortiGate instance. Default is false. <br/>  - ums: (Optional\|map) Configurations for UMS mode.<br/>    Options for ums:<br/>    - autoscale\_psksecret : (Required\|string) Password that will used on the auto-scale sync-up.<br/>    - fmg\_password : (Required\|string) FortiManager password.<br/>    - hb\_interval : (Optional\|number) Time between sending heartbeat packets. Increase to reduce false positives. Default: 10.<br/>    - api\_key : (Optional\|string) FortiManager API key that used and required when license\_type is 'byol'. | <pre>object({<br/>    ip                  = string<br/>    sn                  = string<br/>    fgt_lic_mgmt        = optional(string, "fmg")<br/>    vrf_select          = optional(number)<br/>    primary_only        = optional(bool, false)<br/>    ums = optional(object({<br/>      autoscale_psksecret = optional(string, "")<br/>      fmg_password        = optional(string, "")<br/>      hb_interval         = optional(number, 10)<br/>      api_key             = optional(string, "")<br/>    }))<br/>  })</pre> | `null` | no |
| <a name="input_fortiflex_configid_list"></a> [fortiflex\_configid\_list](#input\_fortiflex\_configid\_list) | Config ID list from FortiFlex account that used to activate FortiGate instance. | `list` | `[]` | no |
| <a name="input_fortiflex_password"></a> [fortiflex\_password](#input\_fortiflex\_password) | Password of FortiFlex API user. | `string` | `null` | no |
| <a name="input_fortiflex_refresh_token"></a> [fortiflex\_refresh\_token](#input\_fortiflex\_refresh\_token) | Refresh token used for FortiFlex. | `string` | `null` | no |
| <a name="input_fortiflex_sn_list"></a> [fortiflex\_sn\_list](#input\_fortiflex\_sn\_list) | Serial number list from FortiFlex account that used to activate FortiGate instance. | `list` | `[]` | no |
| <a name="input_fortiflex_username"></a> [fortiflex\_username](#input\_fortiflex\_username) | Username of FortiFlex API user. | `string` | `null` | no |
| <a name="input_gwlb_ips"></a> [gwlb\_ips](#input\_gwlb\_ips) | Gateway Load Balancer IPs that used for FortiGate configuration.<br/>Format:<pre>gwlb_ips = {<br/>        \<Subnet_id\> = \<IP\><br/>  }</pre>Example:<pre>gwlb_ips = {<br/>  subnet-12345678 = 10.0.0.47<br/>}</pre> | `map(string)` | `{}` | no |
| <a name="input_health_check_port"></a> [health\_check\_port](#input\_health\_check\_port) | Load balancer health check port. | `number` | `0` | no |
| <a name="input_health_check_protocol"></a> [health\_check\_protocol](#input\_health\_check\_protocol) | Load balancer health check protocol. | `string` | `""` | no |
| <a name="input_instance_type"></a> [instance\_type](#input\_instance\_type) | Provide the instance type for the FortiGate instances | `string` | `"c6i.xlarge"` | no |
| <a name="input_keypair_name"></a> [keypair\_name](#input\_keypair\_name) | The keypair name that used in FortiGate EC2 instance. | `string` | n/a | yes |
| <a name="input_lambda_timeout"></a> [lambda\_timeout](#input\_lambda\_timeout) | Amount of time your Lambda Function has to run in seconds. Defaults to 300. | `number` | `300` | no |
| <a name="input_lic_folder_path"></a> [lic\_folder\_path](#input\_lic\_folder\_path) | Folder path of FortiGate license files or token json file. | `string` | `null` | no |
| <a name="input_lic_s3_name"></a> [lic\_s3\_name](#input\_lic\_s3\_name) | AWS S3 bucket name that contains FortiGate license files or token json file. | `string` | `null` | no |
| <a name="input_license_type"></a> [license\_type](#input\_license\_type) | Provide the license type for the FortiGate instances. Options: on\_demand, byol. Default is on\_demand. | `string` | `"on_demand"` | no |
| <a name="input_metadata_options"></a> [metadata\_options](#input\_metadata\_options) | The metadata options for the instances.<br/>Options:<br/>  - http\_endpoint               : (Optional\|string) Whether the metadata service is available. Can be "enabled" or "disabled". (Default: "enabled").<br/>  - http\_tokens                 : (Optional\|string) Whether or not the metadata service requires session tokens, also referred to as Instance Metadata Service Version 2 (IMDSv2). Can be "optional" or "required". (Default: "optional").<br/>  - http\_put\_response\_hop\_limit : (Optional\|number) The desired HTTP PUT response hop limit for instance metadata requests. The larger the number, the further instance metadata requests can travel. Can be an integer from 1 to 64. (Default: 1).<br/>  - http\_protocol\_ipv6          : (Optional\|string) Enables or disables the IPv6 endpoint for the instance metadata service. Can be "enabled" or "disabled".<br/>  - instance\_metadata\_tags      : (Optional\|string) Enables or disables access to instance tags from the instance metadata service. Can be "enabled" or "disabled".<br/>Format:<pre>metadata_options = {<br/>      \<Option name\> = ""<br/>  }</pre> | <pre>object({<br/>    http_endpoint = optional(string, "enabled")<br/>    http_tokens   = optional(string, "optional")<br/>    http_put_response_hop_limit = optional(number, 1)<br/>    http_protocol_ipv6 = optional(string, null)<br/>    instance_metadata_tags  = optional(string, null)<br/>  })</pre> | `null` | no |
| <a name="input_mgmt_intf_index"></a> [mgmt\_intf\_index](#input\_mgmt\_intf\_index) | Management interface device index that will used on Lambda function to connect with FortiGate instance. | `number` | `0` | no |
| <a name="input_module_prefix"></a> [module\_prefix](#input\_module\_prefix) | Prefix that will be used in the whole module. | `string` | `""` | no |
| <a name="input_network_interfaces"></a> [network\_interfaces](#input\_network\_interfaces) | Network interfaces configuration for FortiGate VM instance.<br/>Format:<pre>network_interfaces = {<br/>      \<Key\> = {<br/>          \<Option\> = \<Option value\><br/>      }<br/>  }</pre>Key:<br/>  Name of the interface.<br/>Options:<br/>  - device\_index       : (Required\|int) Integer to define the network interface index. Interface with `0` will be attached at boot time.<br/>  - subnet\_id\_map      : (Required\|map) Subnet ID map to create the ENI in. The key is the Availability Zone name of the subnet, and the value is the Subnet ID.<br/>  - vdom               : (Optional\|string) Vdom name that the interface belongs to. Only works when vdom mode is multi-vdom. Default will be root if not set and vdom mode is multi-vdom.<br/>  - description        : (Optional\|string) Description for the network interface.<br/>  - to\_gwlb            : (Optional\|bool) If set to true, that means this port is connected to the Gateway Load Balancer.<br/>  - private\_ips        : (Optional\|list) List of private IPs to assign to the ENI without regard to order.<br/>  - source\_dest\_check  : (Optional\|bool) Whether to enable source destination checking for the ENI. Defaults false.<br/>  - security\_groups    : (Optional\|list) List of security group IDs to assign to the ENI. Defaults null.<br/>  - enable\_public\_ip   : (Optional\|bool) Whether to assign a public IP for the ENI. Defaults to false.<br/>  - public\_ipv4\_pool   : (Optional\|string) Specify EC2 IPv4 address pool. If not set, Amazon's poll will be used. Only useful when `enable_public_ip` is set to true.<br/>  - existing\_eip\_id    : (Optional\|string) Associate an existing EIP to the ENI. Sould set enable\_public\_ip to false.<br/>  - mgmt\_intf          : (Optional\|bool) Whether this interface is management interface. If set to true, will set defaultgw to true for this interface on FortiGate instance. Default is false.<br/><br/>Example:<pre>network_interfaces = {<br/>  mgmt = {<br/>    device_index       = 1<br/>    subnet_id_map          = {<br/>      \<AZ_NAME\> = \<SUBNET_ID\><br/>    }<br/>    enable_public_ip   = true<br/>    source_dest_check  = true<br/>    security_groups = ["\<SECURITY_GROUP_ID\>"]<br/>  },<br/>  public1 = {<br/>    device_index     = 0<br/>    subnet_id_map        = {<br/>      \<AZ_NAME\> = \<SUBNET_ID\><br/>    }<br/>    existing_eip_id  = \<ELISTIC_IP_ID\><br/>  }<br/>}</pre> | `any` | n/a | yes |
| <a name="input_primary_scalein_protection"></a> [primary\_scalein\_protection](#input\_primary\_scalein\_protection) | If true, will set scale-in protection for the primary instance. Only works when enable\_fgt\_system\_autoscale set to true. Default is false. | `bool` | `false` | no |
| <a name="input_scale_policies"></a> [scale\_policies](#input\_scale\_policies) | Auto Scaling group scale policies.<br/>Format:<pre>scale_policies = {<br/>      \<Policy name\> = {<br/>          \<Option\> = \<Option value\><br/>      }<br/>  }</pre>Options:<br/>  - policy\_type               : (Required\|string) Policy type, either "SimpleScaling", "StepScaling", "TargetTrackingScaling", or "PredictiveScaling".<br/>  - adjustment\_type           : (Optional\|string) Whether the adjustment is an absolute number or a percentage of the current capacity. Valid values are ChangeInCapacity, ExactCapacity, and PercentChangeInCapacity.<br/>  Options only for SimpleScaling:<br/>  - cooldown           : (Optional\|number) Amount of time, in seconds, after a scaling activity completes and before the next scaling activity can start.<br/>  - scaling\_adjustment : (Optional\|string) Number of instances by which to scale. adjustment\_type determines the interpretation of this number (e.g., as an absolute number or as a percentage of the existing Auto Scaling group size). A positive increment adds to the current capacity and a negative value removes from the current capacity.<br/>  Options only for TargetTrackingScaling:<br/>  - target\_tracking\_configuration : (Optional\|map) Target tracking policy.<br/>    Options for parameter target\_tracking\_configuration:<br/>    - target\_value                    : (Required\|number) Target value for the metric.<br/>    - disable\_scale\_in                : (Optional\|bool) Whether scale in by the target tracking policy is disabled. Default: false.<br/>    - estimated\_instance\_warmup : (Optional\|number) Estimated time, in seconds, until a newly launched instance will contribute CloudWatch metrics.<br/>    - predefined\_metric\_specification : (Optional\|map) Predefined metric.<br/>      Options for parameter predefined\_metric\_specification:<br/>      - predefined\_metric\_type : (Required\|string) Metric type.<br/>      - resource\_label         : (Optional\|string) Identifies the resource associated with the metric type.<br/><br/>Example:<pre>scale_policies = {<br/>    cpu_above_80 = {<br/>        policy_type               = "TargetTrackingScaling"<br/>        estimated_instance_warmup = 60<br/>        target_tracking_configuration = {<br/>          target_value = 80<br/>          predefined_metric_specification = {<br/>            predefined_metric_type = "ASGAverageCPUUtilization"<br/>          }<br/>        }<br/>    }<br/>}</pre> | `any` | `{}` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags that applies to related resources.<br/>Format:<pre>tags = {<br/>      \<Option\> = \<Option value\><br/>  }</pre>Options:<br/>  - general     :  Tags will add to all resources.<br/>  - template    :  Tags for launch template.<br/>  - instance    :  Tags for FortiGate instance.<br/>  - asg         :  Tags for Auto Scaling Group.<br/>  - lambda      :  Tags for Lambda function.<br/>  - iam         :  Tags for IAM related resources.<br/>  - dynamodb    :  Tags for DynamoDB related resources.<br/>  - s3          :  Tags for S3 related resources.<br/>  - cloudwatch  :  Tags for CloudWatch related resources.<br/><br/>Example:<pre>tags = {<br/>  general = {<br/>    Created_from = "Terraform"<br/>  },<br/>  template = {<br/>    Used_to = "ASG"<br/>  }<br/>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_template_name"></a> [template\_name](#input\_template\_name) | The name of the launch template. If you leave this blank, Terraform will auto-generate a unique name. | `string` | `""` | no |
| <a name="input_user_conf"></a> [user\_conf](#input\_user\_conf) | User configuration in CLI format that will applied to the FortiGate instance. | `string` | `""` | no |
| <a name="input_user_conf_s3"></a> [user\_conf\_s3](#input\_user\_conf\_s3) | User configuration files in AWS S3 that will applied to FortiGate instance.<br/>The key is the Bucket name, and the value is a list of key names in this Bucket.<br/>Format:<pre>user_conf_s3 = {<br/>      \<Bucket name\> = []<br/>  }</pre> | `map(list(string))` | `{}` | no |
| <a name="input_vpc_id"></a> [vpc\_id](#input\_vpc\_id) | The VPC ID for this ASG. | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_asg_group"></a> [asg\_group](#output\_asg\_group) | n/a |
| <a name="output_asg_policy_list"></a> [asg\_policy\_list](#output\_asg\_policy\_list) | n/a |
| <a name="output_dynamodb_table_name"></a> [dynamodb\_table\_name](#output\_dynamodb\_table\_name) | n/a |
| <a name="output_lic_s3_name"></a> [lic\_s3\_name](#output\_lic\_s3\_name) | n/a |

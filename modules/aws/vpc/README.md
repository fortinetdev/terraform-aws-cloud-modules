## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.3, < 2.0.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | n/a |
| <a name="provider_null"></a> [null](#provider\_null) | n/a |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_internet_gateway.igw](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/internet_gateway) | resource |
| [aws_security_group.secgrp](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group) | resource |
| [aws_subnet.subnets](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet) | resource |
| [aws_vpc.vpc](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc) | resource |
| [null_resource.validation_check_vpc](https://registry.terraform.io/providers/hashicorp/null/latest/docs/resources/resource) | resource |
| [aws_internet_gateway.igw](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/internet_gateway) | data source |
| [aws_vpc.vpc](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/vpc) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_assign_generated_ipv6_cidr_block"></a> [assign\_generated\_ipv6\_cidr\_block](#input\_assign\_generated\_ipv6\_cidr\_block) | Requests an Amazon-provided IPv6 CIDR block with a /56 prefix length for the VPC. You cannot specify the range of IP addresses, or the size of the CIDR block. Default is false. | `bool` | `false` | no |
| <a name="input_enable_dns_hostnames"></a> [enable\_dns\_hostnames](#input\_enable\_dns\_hostnames) | A boolean flag to enable/disable DNS hostnames in the VPC. Defaults false. | `bool` | `false` | no |
| <a name="input_enable_dns_support"></a> [enable\_dns\_support](#input\_enable\_dns\_support) | A boolean flag to enable/disable DNS support in the VPC. Defaults to true. | `bool` | `true` | no |
| <a name="input_existing_igw"></a> [existing\_igw](#input\_existing\_igw) | Using existing IGW. <br>If the id is specified, will use this IGW ID. Otherwise, will search the IGW based on the given infomation.<br>Options:<br>    - id         :  ID of the specific IGW.<br>    - name       :  Name of the specific IGW to retrieve.<br>    - tags       :  Map of tags, each pair of which must exactly match a pair on the desired IGW.<br>    <br>Example:<pre>existing_igw = {<br>    name = "Security_IGW"<br>    tags = {<br>        \<Option\> = \<Option value\><br>    }<br>}</pre> | `any` | `null` | no |
| <a name="input_existing_vpc"></a> [existing\_vpc](#input\_existing\_vpc) | Using existing VPC. <br>If the id is specified, will use this VPC ID. Otherwise, will search the VPC based on the given infomation.<br>Options:<br>    - cidr\_block :  Cidr block of the desired VPC.<br>    - id         :  ID of the specific VPC.<br>    - name       :  Name of the specific VPC to retrieve.<br>    - tags       :  Map of tags, each pair of which must exactly match a pair on the desired VPC.<br>    <br>Example:<pre>existing_vpc = {<br>    name = "Security_VPC"<br>    tags = {<br>        \<Option\> = \<Option value\><br>    }<br>}</pre> | `any` | `null` | no |
| <a name="input_igw_name"></a> [igw\_name](#input\_igw\_name) | Internet Gateway name. Default empty string, which means do not create IGW. | `string` | `""` | no |
| <a name="input_instance_tenancy"></a> [instance\_tenancy](#input\_instance\_tenancy) | A tenancy option for instances launched into the VPC. <br>Default is default, which ensures that EC2 instances launched in this VPC use the EC2 instance tenancy attribute specified when the EC2 instance is launched. <br>The only other option is dedicated, which ensures that EC2 instances launched in this VPC are run on dedicated tenancy instances regardless of the tenancy attribute specified at launch. <br>This has a dedicated per region fee of $2 per hour, plus an hourly per instance usage fee. | `string` | `"default"` | no |
| <a name="input_security_groups"></a> [security\_groups](#input\_security\_groups) | Security groups configuration for the target VPC.<br>Format:<pre>security_groups = {<br>        \<Security group name\> = {<br>            description = "\<Description\>"<br>            ingress     = {<br>                \<Rule name1\> = {<br>                    \<Option\> = \<Option value\><br>                }<br>            }<br>            egress     = {<br>                \<Rule name1\> = {<br>                    \<Option\> = \<Option value\><br>                }<br>            }<br>        }<br>    }</pre>Security groups options:<br>    - description  : (Optional\|string) Security group description. Cannot be empty string(""), and also can not be updated after created. This field maps to the AWS `GroupDescription` attribute, for which there is no Update API. If you'd like to classify your security groups in a way that can be updated, use `tags`.<br>    - ingress      : (Optional\|map) Configuration block for ingress rules.<br>    - egress       : (Optional\|map) Configuration block for egress rules.<br><br>Ingress options:<br>    - from\_port         : (Required\|string) Start port (or ICMP type number if protocol is icmp or icmpv6).<br>    - to\_port           : (Required\|string) End range port (or ICMP code if protocol is icmp).<br>    - protocol          : (Required\|string) Protocol.<br>    - cidr\_blocks       : (Optional\|list)  List of CIDR blocks.<br>    - description       : (Optional\|string) Description of this ingress rule.<br>    - ipv6\_cidr\_blocks  : (Optional\|list) List of IPv6 CIDR blocks.<br>    - prefix\_list\_ids   : (Optional\|list) List of Prefix List IDs.<br>    - security\_groups   : (Optional\|list) List of security groups. A group name can be used relative to the default VPC. Otherwise, group ID.<br>    <br>Egress options:<br>    - from\_port         : (Required\|string) Start port (or ICMP type number if protocol is icmp).<br>    - to\_port           : (Required\|string) End range port (or ICMP code if protocol is icmp).<br>    - protocol          : (Required\|string) Protocol.<br>    - cidr\_blocks       : (Optional\|list)  List of CIDR blocks.<br>    - description       : (Optional\|string) Description of this egress rule.<br>    - ipv6\_cidr\_blocks  : (Optional\|list) List of IPv6 CIDR blocks.<br>    - prefix\_list\_ids   : (Optional\|list) List of Prefix List IDs.<br>    - security\_groups   : (Optional\|list) List of security groups. A group name can be used relative to the default VPC. Otherwise, group ID.<br>    <br>Example:<pre>security_groups = {<br>    secgrp1 = {<br>        description = "Security group by Terraform"<br>        ingress     = {<br>            https = {<br>                from_port         = "443"<br>                to_port           = "443"<br>                protocol          = "tcp"<br>                cidr_blocks       = [ "0.0.0.0/0" ]<br>            }<br>        }<br>        egress     = {<br>            all_traffic = {<br>                from_port         = "0"<br>                to_port           = "0"<br>                protocol          = "tcp"<br>                cidr_blocks       = [ "0.0.0.0/0" ]<br>            }<br>        }<br>    }<br>}</pre> | `any` | `{}` | no |
| <a name="input_subnets"></a> [subnets](#input\_subnets) | Subnets configuration for the target VPC.<br>Format:<pre>subnets = {<br>        \<Subnet name\> = {<br>            \<Option\> = \<Option value\><br>        }<br>    }</pre>Subnet options:<br>    - cidr\_block  : (Optional\|string) The IPv4 CIDR block for the subnet.<br>    - availability\_zone  : (Optional\|string) AZ for the subnet.<br>    - map\_public\_ip\_on\_launch  : (Optional\|string) Specify true to indicate that instances launched into the subnet should be assigned a public IP address. Default is false.<br>Example:<pre>subnets = {<br>    fgt_asg = {<br>        cidr_block = "10.0.1.0/24"<br>        availability_zone = "us-west-2a"<br>    }<br>}</pre> | `any` | `{}` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags that applies to related resources.<br>Format:<pre>tags = {<br>      <Option> = <Option value><br>  }</pre>Options:<br>  - general         :  Tags will add to all resources.<br>  - vpc             :  Tags for VPC.<br>  - igw             :  Tags for Internet gateway.<br>  - security\_group  :  Tags for Security group.<br>  - subnet          :  Tags for Subnets.<br><br>Example:<pre>tags = {<br>  general = {<br>    Created_from = "Terraform"<br>  },<br>  vpc = {<br>    Used_to = "ASG"<br>  }<br>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_vpc_cidr_block"></a> [vpc\_cidr\_block](#input\_vpc\_cidr\_block) | The IPv4 CIDR block for the VPC. | `string` | n/a | yes |
| <a name="input_vpc_name"></a> [vpc\_name](#input\_vpc\_name) | VPC name. | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_igw"></a> [igw](#output\_igw) | n/a |
| <a name="output_security_group"></a> [security\_group](#output\_security\_group) | n/a |
| <a name="output_subnets"></a> [subnets](#output\_subnets) | n/a |
| <a name="output_vpc_id"></a> [vpc\_id](#output\_vpc\_id) | n/a |

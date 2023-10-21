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
| [aws_route.routes](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route) | resource |
| [aws_route_table.rt](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table) | resource |
| [aws_route_table_association.rt_a_gateways](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table_association) | resource |
| [aws_route_table_association.rt_a_subnets](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table_association) | resource |
| [aws_route_table.rt](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/route_table) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_existing_rt"></a> [existing\_rt](#input\_existing\_rt) | Using existing route table. <br>If the id is specified, will use this route table ID. Otherwise, will search the route table based on the given infomation.<br>Options:<br>    - id         :  ID of the specific route table.<br>    - name       :  Name of the specific Vroute tablePC to retrieve.<br>    - tags       :  Map of tags, each pair of which must exactly match a pair on the desired route table.<br>    <br>Example:<pre>existing_rt = {<br>    name = "default_route"<br>    tags = {<br>        \<Option\> = \<Option value\><br>    }<br>}</pre> | `any` | `null` | no |
| <a name="input_routes"></a> [routes](#input\_routes) | Route entries configuration for the target route table.<br>Format:<pre>routes = {<br>        \<Route entry name\> = {<br>            \<Option\> = \<Option value\><br>        }<br>    }</pre>Route entry options:<br>    One of the following destination arguments must be supplied:<br>        - destination\_cidr\_block      : (Optional\|string) The destination CIDR block.<br>        - destination\_ipv6\_cidr\_block : (Optional\|string) The destination IPv6 CIDR block.<br>        - destination\_prefix\_list\_id  : (Optional\|string) The ID of a managed prefix list destination.<br>    One of the following target arguments must be supplied:<br>        - carrier\_gateway\_id          : (Optional\|string) Identifier of a carrier gateway. This attribute can only be used when the VPC contains a subnet which is associated with a Wavelength Zone.<br>        - core\_network\_arn            : (Optional\|string) The Amazon Resource Name (ARN) of a core network.<br>        - egress\_only\_gateway\_id      : (Optional\|string) Identifier of a VPC Egress Only Internet Gateway.<br>        - gateway\_id                  : (Optional\|string) Identifier of a VPC internet gateway or a virtual private gateway.<br>        - nat\_gateway\_id              : (Optional\|string) Identifier of a VPC NAT gateway.<br>        - local\_gateway\_id            : (Optional\|string) Identifier of a Outpost local gateway.<br>        - network\_interface\_id        : (Optional\|string) Identifier of an EC2 network interface.<br>        - transit\_gateway\_id          : (Optional\|string) Identifier of an EC2 Transit Gateway.<br>        - vpc\_endpoint\_id             : (Optional\|string) Identifier of a VPC Endpoint.<br>        - vpc\_peering\_connection\_id   : (Optional\|string) Identifier of a VPC peering connection.<br>Example:<pre>routes = {<br>    to_igw = {<br>        destination_cidr_block = "0.0.0.0/0"<br>        gateway_id = "igw-12345678"<br>    }<br>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_rt_association_gateways"></a> [rt\_association\_gateways](#input\_rt\_association\_gateways) | Gateway IDs to associate to current route table. | `list(string)` | `[]` | no |
| <a name="input_rt_association_subnets"></a> [rt\_association\_subnets](#input\_rt\_association\_subnets) | Subnet IDs to associate to current route table. | `list(string)` | `[]` | no |
| <a name="input_rt_name"></a> [rt\_name](#input\_rt\_name) | The route table name. | `string` | `null` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags that applies to related resources.<br>Format:<pre>tags = {<br>      \<Option\> = \<Option value\><br>  }</pre>Options:<br>  - general :  Tags will add to all resources.<br>  - rt      :  Tags for route table.<br><br>Example:<pre>tags = {<br>  general = {<br>    Created_from = "Terraform"<br>  },<br>  rt = {<br>    Used_to = "ASG"<br>  }<br>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_vpc_id"></a> [vpc\_id](#input\_vpc\_id) | The VPC ID. | `string` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_route_table"></a> [route\_table](#output\_route\_table) | n/a |
| <a name="output_routes"></a> [routes](#output\_routes) | n/a |
| <a name="output_rt_association"></a> [rt\_association](#output\_rt\_association) | n/a |

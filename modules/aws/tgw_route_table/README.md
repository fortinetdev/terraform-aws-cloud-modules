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
| [aws_ec2_transit_gateway_route.tgw_routes](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ec2_transit_gateway_route) | resource |
| [aws_ec2_transit_gateway_route_table.tgw_rt](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ec2_transit_gateway_route_table) | resource |
| [aws_ec2_transit_gateway_route_table_association.tgw_rt_a](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ec2_transit_gateway_route_table_association) | resource |
| [aws_ec2_transit_gateway_route_table_propagation.tgw_rt_p](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ec2_transit_gateway_route_table_propagation) | resource |
| [aws_ec2_transit_gateway_route_table.tgw_rt](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ec2_transit_gateway_route_table) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_existing_tgw_rt"></a> [existing\_tgw\_rt](#input\_existing\_tgw\_rt) | Using existing Transit Gateway route table. <br>If the id is specified, will use this Transit Gateway route table ID. Otherwise, will search the route table based on the given infomation.<br>Options:<br>    - id     :  ID of the specific route table.<br>    - filter :  One or more configuration blocks containing name-values filters. Note: the value should be a list.<br>    <br>Example:<pre>existing_tgw_rt = {<br>    filter = {<br>        Name = [ "default_route" ]<br>    }<br>}</pre> | `any` | `null` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags that applies to related resources.<br>Format:<pre>tags = {<br>      \<Option\> = \<Option value\><br>  }</pre>Options:<br>  - general :  Tags will add to all resources.<br>  - tgw\_rt      :  Tags for route table.<br><br>Example:<pre>tags = {<br>  general = {<br>    Created_from = "Terraform"<br>  },<br>  tgw_rt = {<br>    Used_to = "ASG"<br>  }<br>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_tgw_id"></a> [tgw\_id](#input\_tgw\_id) | The Transit Gateway ID. | `string` | `null` | no |
| <a name="input_tgw_routes"></a> [tgw\_routes](#input\_tgw\_routes) | Route entries configuration for the target Transit Gateway route table.<br>Format:<pre>tgw_routes = {<br>        \<Route entry name\> = {<br>            \<Option\> = \<Option value\><br>        }<br>    }</pre>Route entry options:<br>    - destination\_cidr\_block        : (Required\|string) IPv4 or IPv6 RFC1924 CIDR used for destination matches. Routing decisions are based on the most specific match.<br>    - transit\_gateway\_attachment\_id : (Optional\|string) Identifier of EC2 Transit Gateway Attachment (required if blackhole is set to false).<br>    - blackhole                     : (Optional\|bool) Indicates whether to drop traffic that matches this route (default to false).<br>Example:<pre>tgw_routes = {<br>    to_secvpc = {<br>        destination_cidr_block = "0.0.0.0/0"<br>        transit_gateway_attachment_id = "tgw-attach-12345678"<br>    }<br>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_tgw_rt_associations"></a> [tgw\_rt\_associations](#input\_tgw\_rt\_associations) | Associations to current Transit Gateway route table. | `list(string)` | `[]` | no |
| <a name="input_tgw_rt_name"></a> [tgw\_rt\_name](#input\_tgw\_rt\_name) | The Transit Gateway route table name. | `string` | `null` | no |
| <a name="input_tgw_rt_propagations"></a> [tgw\_rt\_propagations](#input\_tgw\_rt\_propagations) | Propagations to current Transit Gateway route table. | `list(string)` | `[]` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_tgw_routes"></a> [tgw\_routes](#output\_tgw\_routes) | n/a |
| <a name="output_tgw_rt_id"></a> [tgw\_rt\_id](#output\_tgw\_rt\_id) | n/a |

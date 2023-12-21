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
| [aws_ec2_transit_gateway.tgw](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ec2_transit_gateway) | resource |
| [aws_ec2_transit_gateway_vpc_attachment.tgw_attachments](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ec2_transit_gateway_vpc_attachment) | resource |
| [null_resource.validation_check_tgw](https://registry.terraform.io/providers/hashicorp/null/latest/docs/resources/resource) | resource |
| [aws_ec2_transit_gateway.tgw](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ec2_transit_gateway) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_amazon_side_asn"></a> [amazon\_side\_asn](#input\_amazon\_side\_asn) | Private Autonomous System Number (ASN) for the Amazon side of a BGP session. The range is 64512 to 65534 for 16-bit ASNs and 4200000000 to 4294967294 for 32-bit ASNs. Default value: 64512. | `string` | `"64512"` | no |
| <a name="input_auto_accept_shared_attachments"></a> [auto\_accept\_shared\_attachments](#input\_auto\_accept\_shared\_attachments) | Whether resource attachment requests are automatically accepted. Valid values: disable, enable. Default value: disable. | `string` | `"disable"` | no |
| <a name="input_default_route_table_association"></a> [default\_route\_table\_association](#input\_default\_route\_table\_association) | Whether resource attachments are automatically associated with the default association route table. Valid values: disable, enable. Default value: enable. | `string` | `"enable"` | no |
| <a name="input_default_route_table_propagation"></a> [default\_route\_table\_propagation](#input\_default\_route\_table\_propagation) | Whether resource attachments automatically propagate routes to the default propagation route table. Valid values: disable, enable. Default value: enable. | `string` | `"enable"` | no |
| <a name="input_dns_support"></a> [dns\_support](#input\_dns\_support) | Whether DNS support is enabled. Valid values: disable, enable. Default value: enable. | `string` | `"enable"` | no |
| <a name="input_existing_tgw"></a> [existing\_tgw](#input\_existing\_tgw) | Using existing Transit gateway. <br>If the id is specified, will use this Transit gateway ID. Otherwise, will search the Transit gateway based on the given infomation.<br>Options:<br>    - id     :  (Optional\|string) ID of the specific Transit gateway.<br>    - filter :  (Optional\|map) Map of the filters. Value should be a list.   <br>Example:<pre>existing_tgw = {<br>    filter = {<br>        "options.amazon-side-asn" = ["64512"]<br>    }<br>}</pre> | `any` | `null` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags that applies to related resources.<br>Format:<pre>tags = {<br>      \<Option\> = \<Option value\><br>  }</pre>Options:<br>  - general         :  Tags will add to all resources.<br>  - tgw             :  Tags for Transit gateway.<br>  - tgw\_attachment  :  Tags for Transit gateway attachment.<br><br>Example:<pre>tags = {<br>  general = {<br>    Created_from = "Terraform"<br>  },<br>  tgw = {<br>    Used_to = "ASG"<br>  }<br>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_tgw_attachments"></a> [tgw\_attachments](#input\_tgw\_attachments) | Transit gateway VPC attachments for the Transit gateway. <br>Format:<pre>tgw_attachments = {<br>        \<Attachment name\> = {<br>            subnet_ids         = \<Subnet_id\>  <br>            transit_gateway_id = \<Transit_gateway_id\><br>            vpc_id             = \<VPC_id\> <br>            \<Option\> = \<Option value\><br>        }<br>    }</pre>Options:<br>    - subnet\_ids                                      : (Required\|list) Identifiers of EC2 Subnets.<br>    - vpc\_id                                          : (Required\|string) Identifier of EC2 VPC.<br>    - appliance\_mode\_support                          : (Optional\|string) Whether Appliance Mode support is enabled. If enabled, a traffic flow between a source and destination uses the same Availability Zone for the VPC attachment for the lifetime of that flow. Valid values: disable, enable. Default value: disable.<br>    - dns\_support                                     : (Optional\|string) Whether DNS support is enabled. Valid values: disable, enable. Default value: enable.<br>    - ipv6\_support                                    : (Optional\|string) Whether IPv6 support is enabled. Valid values: disable, enable. Default value: disable.<br>    - transit\_gateway\_default\_route\_table\_association : (Optional\|bool) Boolean whether the VPC Attachment should be associated with the EC2 Transit Gateway association default route table. This cannot be configured or perform drift detection with Resource Access Manager shared EC2 Transit Gateways. Default value: true.<br>    - transit\_gateway\_default\_route\_table\_propagation : (Optional\|bool) Boolean whether the VPC Attachment should propagate routes with the EC2 Transit Gateway propagation default route table. This cannot be configured or perform drift detection with Resource Access Manager shared EC2 Transit Gateways. Default value: true.<br><br>Example:<pre>tgw_attachments = {<br>    security_vpc = {<br>        subnet_ids         = \<Subnet_id\>  <br>        vpc_id             = \<VPC_id\> <br>    }<br>}</pre> | `any` | `{}` | no |
| <a name="input_tgw_description"></a> [tgw\_description](#input\_tgw\_description) | Description of the EC2 Transit Gateway. | `string` | `""` | no |
| <a name="input_tgw_name"></a> [tgw\_name](#input\_tgw\_name) | Transit gateway name | `string` | `""` | no |
| <a name="input_vpn_ecmp_support"></a> [vpn\_ecmp\_support](#input\_vpn\_ecmp\_support) | Whether VPN Equal Cost Multipath Protocol support is enabled. Valid values: disable, enable. Default value: enable. | `string` | `"enable"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_tgw"></a> [tgw](#output\_tgw) | n/a |
| <a name="output_tgw_attachments"></a> [tgw\_attachments](#output\_tgw\_attachments) | n/a |

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
| [aws_eip.ngw_eips](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eip) | resource |
| [aws_nat_gateway.ngw](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/nat_gateway) | resource |
| [aws_nat_gateway.ngw](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/nat_gateway) | data source |
| [aws_subnet.ngw_subnet](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_allocate_eip"></a> [allocate\_eip](#input\_allocate\_eip) | Boolean whether allocate an EIP to the Nat Gateway. Default is true. | `bool` | `true` | no |
| <a name="input_connectivity_type"></a> [connectivity\_type](#input\_connectivity\_type) | Connectivity type for the gateway. Valid values are private and public. Defaults to public. | `string` | `"public"` | no |
| <a name="input_customer_owned_ipv4_pool"></a> [customer\_owned\_ipv4\_pool](#input\_customer\_owned\_ipv4\_pool) | ID of a customer-owned address pool. | `string` | `null` | no |
| <a name="input_domain"></a> [domain](#input\_domain) | Indicates if this EIP is for use in VPC. Defaults to vpc. | `string` | `"vpc"` | no |
| <a name="input_existing_eip_id"></a> [existing\_eip\_id](#input\_existing\_eip\_id) | An existing EIP that allocate to the Nat Gateway. | `string` | `null` | no |
| <a name="input_existing_ngw"></a> [existing\_ngw](#input\_existing\_ngw) | Using existing NAT Gateway. <br>Options:<br>    - id        :  (Optional\|string) ID of the specific NAT Gateway to retrieve.<br>    - subnet\_id :  (Optional\|string) ID of subnet that the NAT Gateway resides in.<br>    - vpc\_id    :  (Optional\|string) ID of the VPC that the NAT Gateway resides in.<br>    - state     :  (Optional\|string) State of the NAT Gateway (pending \| failed \| available \| deleting \| deleted ).<br>    - filter    :  (Optional\|map) Configuration block(s) for filtering. <br>    - tags      :  (Optional\|map) Map of tags, each pair of which must exactly match a pair on the desired VPC Endpoint Service.<br>Example:<pre>existing_ngw = {<br>    id = "nat-1234567789"<br>}</pre> | `any` | `null` | no |
| <a name="input_private_ip"></a> [private\_ip](#input\_private\_ip) | The private IPv4 address to assign to the NAT gateway. If you don't provide an address, a private IPv4 address will be automatically assigned. | `string` | `null` | no |
| <a name="input_public_ipv4_pool"></a> [public\_ipv4\_pool](#input\_public\_ipv4\_pool) | EC2 IPv4 address pool identifier or amazon. | `string` | `"amazon"` | no |
| <a name="input_subnet_id"></a> [subnet\_id](#input\_subnet\_id) | The Subnet ID of the subnet in which to place the gateway. | `string` | `null` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags that applies to related resources.<br>Format:<pre>tags = {<br>      \<Option\> = \<Option value\><br>  }</pre>Options:<br>  - general :  Tags will add to all resources.<br>  - eip     :  Tags for Elastic IP.<br>  - ngw     :  Tags for Nat Gatway.<br><br>Example:<pre>tags = {<br>  general = {<br>    Created_from = "Terraform"<br>  },<br>  ngw = {<br>    Used_to = "ASG"<br>  }<br>}</pre> | `map(map(string))` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_availability_zone"></a> [availability\_zone](#output\_availability\_zone) | n/a |
| <a name="output_nat_gateway"></a> [nat\_gateway](#output\_nat\_gateway) | n/a |

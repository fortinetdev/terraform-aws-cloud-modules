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
| [aws_lb.gwlb](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb) | resource |
| [aws_lb_listener.gwlb_ln](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_listener) | resource |
| [aws_lb_target_group.gwlb_tgp](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_target_group) | resource |
| [aws_lb_target_group_attachment.gwlb_tgp_a](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_target_group_attachment) | resource |
| [aws_vpc_endpoint.gwlb_endps](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint) | resource |
| [aws_vpc_endpoint_service.gwlb_ep_service](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_endpoint_service) | resource |
| [aws_lb.gwlb](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/lb) | data source |
| [aws_lb_target_group.gwlb_tgp](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/lb_target_group) | data source |
| [aws_network_interface.gwlb_intfs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/network_interface) | data source |
| [aws_vpc_endpoint_service.gwlb_ep_service](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/vpc_endpoint_service) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_deregistration_delay"></a> [deregistration\_delay](#input\_deregistration\_delay) | Amount time for Elastic Load Balancing to wait before changing the state of a deregistering target from draining to unused. The range is 0-3600 seconds. The default value is 300 seconds. | `number` | `null` | no |
| <a name="input_enable_cross_zone_load_balancing"></a> [enable\_cross\_zone\_load\_balancing](#input\_enable\_cross\_zone\_load\_balancing) | If true, cross-zone load balancing of the load balancer will be enabled. | `bool` | `null` | no |
| <a name="input_existing_gwlb"></a> [existing\_gwlb](#input\_existing\_gwlb) | Using existing Gateway Load Balancer. <br>Options:<br>    - arn  :  (Optional\|string) Full ARN of the load balancer.<br>    - name :  (Optional\|string) Unique name of the load balancer. <br>    - tags :  (Optional\|map) Mapping of tags, each pair of which must exactly match a pair on the desired load balancer.<br>Example:<pre>existing_gwlb = {<br>    name = "gwlb-fgt"<br>}</pre> | `any` | `null` | no |
| <a name="input_existing_gwlb_ep_service"></a> [existing\_gwlb\_ep\_service](#input\_existing\_gwlb\_ep\_service) | Using existing Gateway Load Balancer VPC Endpoint Service. <br>Options:<br>    - service\_name  :  (Optional\|string) Service name that is specified when creating a VPC endpoint.<br>    - filter        :  (Optional\|map) Configuration block(s) for filtering. <br>    - tags          :  (Optional\|map) Map of tags, each pair of which must exactly match a pair on the desired VPC Endpoint Service.<br>Example:<pre>existing_gwlb_ep_service = {<br>    service_name = "gwlb-tgp-fgt"<br>}</pre> | `any` | `null` | no |
| <a name="input_existing_gwlb_tgp"></a> [existing\_gwlb\_tgp](#input\_existing\_gwlb\_tgp) | Using existing Gateway Load Balancer. <br>Options:<br>    - arn  :  (Optional\|string) Full ARN of the target group.<br>    - name :  (Optional\|string) Unique name of the target group. <br>    - tags :  (Optional\|map) Mapping of tags, each pair of which must exactly match a pair on the desired target group.<br>Example:<pre>existing_gwlb_tgp = {<br>    name = "gwlb-tgp-fgt"<br>}</pre> | `any` | `null` | no |
| <a name="input_gwlb_endps"></a> [gwlb\_endps](#input\_gwlb\_endps) | Gateway Load Balancer Endpoint map. <br>Format:<pre>gwlb_endps = {<br>        \<Endpoint name\> = {<br>            vpc_id         = \<VPC_id\>  <br>            subnet_id = \<Subnet_id\><br>        }<br>    }</pre>Options:<br>    - vpc\_id    : (Required\|string) Identifier of EC2 VPC.<br>    - subnet\_id : (Required\|string) Identifiers of EC2 Subnet.<br> <br>Example:<pre>gwlb_endps = {<br>    gwlbe-secvpc-us-west-1b = {<br>        vpc_id    = "vpc-12345678"<br>        subnet_id = "subnet-123456789"<br>    }<br>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_gwlb_ep_service_name"></a> [gwlb\_ep\_service\_name](#input\_gwlb\_ep\_service\_name) | Gateway Load Balancer Endpoint Service name. | `string` | `""` | no |
| <a name="input_gwlb_ln_name"></a> [gwlb\_ln\_name](#input\_gwlb\_ln\_name) | Gateway Load Balancer Listener name. | `string` | `null` | no |
| <a name="input_gwlb_name"></a> [gwlb\_name](#input\_gwlb\_name) | Gateway Load Balancer name | `string` | `""` | no |
| <a name="input_gwlb_tg_attachments"></a> [gwlb\_tg\_attachments](#input\_gwlb\_tg\_attachments) | Gateway Load Balancer Target Group attachments configuration.<br>Format:<pre>gwlb_tg_attachments = {<br>  "\<Attachment_name\>" = {<br>    \<Option\> = \<Option value\><br>  }<br>}</pre>Options:<br>    - tgp\_target\_id                : (Optional\|string) The ID of the target. This is the Instance ID for an instance, or the container ID for an ECS container. If the target type is ip, specify an IP address. If the target type is lambda, specify the arn of lambda. If the target type is alb, specify the arn of alb.<br>    - tgp\_attach\_port              : (Optional\|string) The port on which targets receive traffic.<br>    - tgp\_attach\_availability\_zone : (Optional\|string) The Availability Zone where the IP address of the target is to be registered. If the private ip address is outside of the VPC scope, this value must be set to 'all'.<br><br>Example:<pre>gwlb_tg_attachments = {<br>  "fgt_instance1" = {<br>    tgp_target_id = i-01563a5f67d4e6010<br>  }<br>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_health_check"></a> [health\_check](#input\_health\_check) | Health Check configuration block.<br>Format:<pre>health_check = {<br>    \<Option\> = \<Option value\><br>}</pre>Options:<br>    - enabled              : (Optional\|bool) Whether health checks are enabled. Defaults to true.<br>    - healthy\_threshold    : (Optional\|number) Number of consecutive health check successes required before considering a target healthy. The range is 2-10. Defaults to 3.<br>    - interval             : (Optional\|number) Approximate amount of time, in seconds, between health checks of an individual target. The range is 5-300. For lambda target groups, it needs to be greater than the timeout of the underlying lambda. Defaults to 30.<br>    - path                 : (Optional\|string) Destination for the health check request. Required for HTTP/HTTPS ALB and HTTP NLB. Only applies to HTTP/HTTPS.<br>    - port                 : (Optional\|number) The port the load balancer uses when performing health checks on targets. Default is traffic-port.<br>    - protocol             : (Optional\|string) Protocol the load balancer uses when performing health checks on targets. Must be either TCP, HTTP, or HTTPS. The TCP protocol is not supported for health checks if the protocol of the target group is HTTP or HTTPS. Defaults to HTTP.<br>    - timeout              : (Optional\|number) Amount of time, in seconds, during which no response from a target means a failed health check. The range is 2-120 seconds. For target groups with a protocol of GENEVE, the default is 5 seconds.<br>    - unhealthy\_threshold  : (Optional\|number) Number of consecutive health check failures required before considering a target unhealthy. The range is 2-10. Defaults to 3.<br><br>Example:<pre>health_check = {<br>    enabled              = true<br>    healthy_threshold    = 3<br>    interval             = 30<br>    port                 = 80<br>    protocol             = "TCP"<br>    timeout              = 5<br>    unhealthy_threshold  = 3<br>}</pre> | `any` | `{}` | no |
| <a name="input_subnets"></a> [subnets](#input\_subnets) | Subnets list for the target Gateway Load Balancer.<br>Example:<pre>subnets = ["subnet-12345678"]</pre> | `list(string)` | `null` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Tags that applies to related resources.<br>Format:<pre>tags = {<br>      \<Option\> = \<Option value\><br>  }</pre>Options:<br>  - general         :  Tags will add to all resources.<br>  - gwlb            :  Tags for Gateway Load Balancer.<br>  - tgp             :  Tags for Target Group.<br>  - gwlb\_ep\_service :  Tags for Gateway Load Balancer Endpoint Service.<br>  - gwlb\_endp       :  Tags for Gateway Load Balancer Endpoints.<br><br>Example:<pre>tags = {<br>  general = {<br>    Created_from = "Terraform"<br>  },<br>  gwlb = {<br>    Used_to = "ASG"<br>  }<br>}</pre> | `map(map(string))` | `{}` | no |
| <a name="input_target_type"></a> [target\_type](#input\_target\_type) | Target type of the target group. Available options: instance, ip, alb, lambda. Default is instance. | `string` | `"instance"` | no |
| <a name="input_tgp_name"></a> [tgp\_name](#input\_tgp\_name) | Target Group name | `string` | `""` | no |
| <a name="input_vpc_id"></a> [vpc\_id](#input\_vpc\_id) | VPC ID for the target group | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_gwlb"></a> [gwlb](#output\_gwlb) | n/a |
| <a name="output_gwlb_endps"></a> [gwlb\_endps](#output\_gwlb\_endps) | n/a |
| <a name="output_gwlb_ips"></a> [gwlb\_ips](#output\_gwlb\_ips) | n/a |
| <a name="output_gwlb_tgp"></a> [gwlb\_tgp](#output\_gwlb\_tgp) | n/a |

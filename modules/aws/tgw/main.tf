locals {
  tgw    = var.existing_tgw == null ? aws_ec2_transit_gateway.tgw[0] : length(var.existing_tgw) == 0 ? aws_ec2_transit_gateway.tgw[0] : data.aws_ec2_transit_gateway.tgw[0]
  tgw_id = local.tgw.id
}

## Transit gateway
data "aws_ec2_transit_gateway" "tgw" {
  count = var.existing_tgw == null ? 0 : length(var.existing_tgw) == 0 ? 0 : 1

  id = lookup(var.existing_tgw, "id", null)
  dynamic "filter" {
    for_each = lookup(var.existing_tgw, "filter", {})
    content {
      name   = filter.key
      values = filter.value
    }
  }
}

resource "aws_ec2_transit_gateway" "tgw" {
  count = var.existing_tgw == null ? 1 : length(var.existing_tgw) == 0 ? 1 : 0

  amazon_side_asn                 = var.amazon_side_asn
  auto_accept_shared_attachments  = var.auto_accept_shared_attachments
  default_route_table_association = var.default_route_table_association
  default_route_table_propagation = var.default_route_table_propagation
  vpn_ecmp_support                = var.vpn_ecmp_support
  dns_support                     = var.dns_support
  description                     = var.tgw_description
  tags = merge(
    {
      Name = var.tgw_name
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "tgw", {})
  )
}

## Transit gateway VPC attachment
resource "aws_ec2_transit_gateway_vpc_attachment" "tgw_attachments" {
  for_each = var.tgw_attachments

  subnet_ids                                      = each.value.subnet_ids
  transit_gateway_id                              = local.tgw_id
  vpc_id                                          = each.value.vpc_id
  appliance_mode_support                          = lookup(each.value, "appliance_mode_support", "disable")
  dns_support                                     = lookup(each.value, "dns_support", "enable")
  ipv6_support                                    = lookup(each.value, "ipv6_support", "disable")
  transit_gateway_default_route_table_association = lookup(each.value, "transit_gateway_default_route_table_association", true)
  transit_gateway_default_route_table_propagation = lookup(each.value, "transit_gateway_default_route_table_propagation", true)
  tags = merge(
    {
      Name = each.key
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "tgw_attachment", {})
  )
}
locals {
  tgw_rt_id = var.existing_tgw_rt == null ? aws_ec2_transit_gateway_route_table.tgw_rt[0].id : contains(keys(var.existing_tgw_rt), "id") ? var.existing_tgw_rt.id : data.aws_ec2_transit_gateway_route_table.tgw_rt[0].id
}

## Transit gatewsy route table
data "aws_ec2_transit_gateway_route_table" "tgw_rt" {
  count = var.existing_tgw_rt == null ? 0 : contains(keys(var.existing_tgw_rt), "id") ? 0 : 1

  dynamic "filter" {
    for_each = var.existing_tgw_rt.filter

    content {
      name   = filter.key
      values = filter.value
    }

  }
}

resource "aws_ec2_transit_gateway_route_table" "tgw_rt" {
  count = var.existing_tgw_rt == null ? 1 : 0

  transit_gateway_id = var.tgw_id
  tags = merge(
    {
      Name = var.tgw_rt_name
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "tgw_rt", {})
  )
}

## Route entries
resource "aws_ec2_transit_gateway_route" "tgw_routes" {
  for_each = var.tgw_routes

  transit_gateway_route_table_id = local.tgw_rt_id
  destination_cidr_block         = each.value.destination_cidr_block
  transit_gateway_attachment_id  = lookup(each.value, "transit_gateway_attachment_id", null)
  blackhole                      = lookup(each.value, "blackhole", false)
}

## Transit Gateway route table association
resource "aws_ec2_transit_gateway_route_table_association" "tgw_rt_a" {
  for_each = { for i, ele in var.tgw_rt_associations : i => ele }

  transit_gateway_route_table_id = local.tgw_rt_id
  transit_gateway_attachment_id  = each.value
}

## Transit Gateway route table propagation
resource "aws_ec2_transit_gateway_route_table_propagation" "tgw_rt_p" {
  for_each = { for i, ele in var.tgw_rt_propagations : i => ele }

  transit_gateway_route_table_id = local.tgw_rt_id
  transit_gateway_attachment_id  = each.value
}


locals {
  rt_id = var.existing_rt == null ? aws_route_table.rt[0].id : contains(keys(var.existing_rt), "id") ? var.existing_rt.id : data.aws_route_table.rt[0].id
}
## VPC route table
data "aws_route_table" "rt" {
  count = var.existing_rt == null ? 0 : contains(keys(var.existing_rt), "id") ? 0 : 1

  tags = merge(
    contains(keys(var.existing_rt), "name") ? {
      Name = var.existing_rt.name
    } : {},
    lookup(var.existing_rt, "tags", {})
  )
}
resource "aws_route_table" "rt" {
  count = var.existing_rt == null ? 1 : 0

  vpc_id = var.vpc_id
  tags = merge(
    {
      Name = var.rt_name
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "rt", {})
  )
}

## Route entries
resource "aws_route" "routes" {
  for_each = var.routes

  route_table_id              = local.rt_id
  destination_cidr_block      = lookup(each.value, "destination_cidr_block", null)
  destination_ipv6_cidr_block = lookup(each.value, "destination_ipv6_cidr_block", null)
  destination_prefix_list_id  = lookup(each.value, "destination_prefix_list_id", null)

  carrier_gateway_id        = lookup(each.value, "carrier_gateway_id", null)
  core_network_arn          = lookup(each.value, "core_network_arn", null)
  egress_only_gateway_id    = lookup(each.value, "egress_only_gateway_id", null)
  gateway_id                = lookup(each.value, "gateway_id", null)
  nat_gateway_id            = lookup(each.value, "nat_gateway_id", null)
  local_gateway_id          = lookup(each.value, "local_gateway_id", null)
  network_interface_id      = lookup(each.value, "network_interface_id", null)
  transit_gateway_id        = lookup(each.value, "transit_gateway_id", null)
  vpc_endpoint_id           = lookup(each.value, "vpc_endpoint_id", null)
  vpc_peering_connection_id = lookup(each.value, "vpc_peering_connection_id", null)
}

## VPC route table association
resource "aws_route_table_association" "rt_a_subnets" {
  count = length(var.rt_association_subnets)

  route_table_id = local.rt_id
  subnet_id      = var.rt_association_subnets[count.index]
}

resource "aws_route_table_association" "rt_a_gateways" {
  count = length(var.rt_association_gateways)

  route_table_id = local.rt_id
  gateway_id     = var.rt_association_gateways[count.index]
}

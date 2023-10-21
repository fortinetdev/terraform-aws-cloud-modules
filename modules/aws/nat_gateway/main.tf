locals {
  allocation_id = var.allocate_eip == false ? null : var.existing_eip_id == null ? aws_eip.ngw_eips[0].id : var.existing_eip_id
}

resource "aws_eip" "ngw_eips" {
  count = var.allocate_eip == false ? 0 : var.existing_eip_id == null ? 1 : 0

  public_ipv4_pool         = var.public_ipv4_pool
  domain                   = var.domain
  customer_owned_ipv4_pool = var.customer_owned_ipv4_pool
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "eip", {})
  )
}

resource "aws_nat_gateway" "ngw" {
  connectivity_type = var.connectivity_type
  allocation_id     = local.allocation_id
  subnet_id         = var.subnet_id
  private_ip        = var.private_ip
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "ngw", {})
  )
}
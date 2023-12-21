locals {
  allocation_id = var.allocate_eip == false ? null : var.existing_eip_id == null ? aws_eip.ngw_eips[0].id : var.existing_eip_id
  ngw           = var.existing_ngw == null ? aws_nat_gateway.ngw[0] : length(coalesce(var.existing_ngw, {})) == 0 ? null : data.aws_nat_gateway.ngw[0]
}

data "aws_nat_gateway" "ngw" {
  count = var.existing_ngw != null && length(coalesce(var.existing_ngw, {})) > 0 ? 1 : 0

  id        = lookup(var.existing_ngw, "id", null)
  subnet_id = lookup(var.existing_ngw, "subnet_id", null)
  vpc_id    = lookup(var.existing_ngw, "vpc_id", null)
  state     = lookup(var.existing_ngw, "state", null)
  tags      = lookup(var.existing_ngw, "tags", null)

  dynamic "filter" {
    for_each = lookup(var.existing_ngw, "filter", {})
    content {
      name   = filter.key
      values = filter.value
    }
  }
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
  count = var.existing_ngw == null ? 1 : 0

  connectivity_type = var.connectivity_type
  allocation_id     = local.allocation_id
  subnet_id         = var.subnet_id
  private_ip        = var.private_ip
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "ngw", {})
  )
}
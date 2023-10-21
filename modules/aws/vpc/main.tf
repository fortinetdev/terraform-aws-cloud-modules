locals {
  vpc_id = var.existing_vpc == null ? aws_vpc.vpc[0].id : contains(keys(var.existing_vpc), "id") ? var.existing_vpc.id : data.aws_vpc.vpc[0].id
}

## VPC
data "aws_vpc" "vpc" {
  count = var.existing_vpc == null ? 0 : contains(keys(var.existing_vpc), "id") ? 0 : 1

  cidr_block = lookup(var.existing_vpc, "cidr_block", null)

  tags = merge(
    contains(keys(var.existing_vpc), "name") ? {
      Name = var.existing_vpc.name
    } : {},
    lookup(var.existing_vpc, "tags", {})
  )
}

resource "aws_vpc" "vpc" {
  count = var.existing_vpc != null ? 0 : 1

  cidr_block                       = var.vpc_cidr_block
  enable_dns_support               = var.enable_dns_support
  enable_dns_hostnames             = var.enable_dns_hostnames
  instance_tenancy                 = var.instance_tenancy
  assign_generated_ipv6_cidr_block = var.assign_generated_ipv6_cidr_block
  tags = merge(
    {
      Name = var.vpc_name
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "vpc", {})
  )
}

## IGW
resource "aws_internet_gateway" "igw" {
  count = var.igw_name == "" ? 0 : 1

  vpc_id = local.vpc_id
  tags = merge(
    {
      Name = var.igw_name
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "igw", {})
  )
}

## Security groups
resource "aws_security_group" "secgrp" {
  for_each = var.security_groups

  name        = each.key
  description = lookup(each.value, "description", null)
  vpc_id      = local.vpc_id
  dynamic "ingress" {
    for_each = lookup(each.value, "ingress", {})

    content {
      from_port        = ingress.value.from_port
      to_port          = ingress.value.to_port
      protocol         = ingress.value.protocol
      cidr_blocks      = lookup(ingress.value, "cidr_blocks", null)
      description      = lookup(ingress.value, "description", null)
      ipv6_cidr_blocks = lookup(ingress.value, "ipv6_cidr_blocks", null)
      prefix_list_ids  = lookup(ingress.value, "prefix_list_ids", null)
      security_groups  = lookup(ingress.value, "security_groups", null)
    }
  }
  dynamic "egress" {
    for_each = lookup(each.value, "egress", {})

    content {
      from_port        = egress.value.from_port
      to_port          = egress.value.to_port
      protocol         = egress.value.protocol
      cidr_blocks      = lookup(egress.value, "cidr_blocks", null)
      description      = lookup(egress.value, "description", null)
      ipv6_cidr_blocks = lookup(egress.value, "ipv6_cidr_blocks", null)
      prefix_list_ids  = lookup(egress.value, "prefix_list_ids", null)
      security_groups  = lookup(egress.value, "security_groups", null)
    }
  }
  tags = merge(
    lookup(var.tags, "general", {}),
    lookup(var.tags, "security_group", {})
  )

  lifecycle {
    create_before_destroy = true
  }
}

## Subnets
resource "aws_subnet" "subnets" {
  for_each = var.subnets

  vpc_id                  = local.vpc_id
  cidr_block              = lookup(each.value, "cidr_block", null)
  availability_zone       = lookup(each.value, "availability_zone", null)
  map_public_ip_on_launch = lookup(each.value, "map_public_ip_on_launch", null)
  tags = merge(
    {
      Name = each.key
    },
    lookup(var.tags, "general", {}),
    lookup(var.tags, "subnet", {})
  )
}


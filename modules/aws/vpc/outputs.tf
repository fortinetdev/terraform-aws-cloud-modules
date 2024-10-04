output "vpc" {
  value = local.vpc
}

output "vpc_id" {
  value = local.vpc_id
}

output "subnets" {
  value = {
    for subnet in aws_subnet.subnets :
    subnet.tags.Name => {
      "id"                = subnet.id
      "availability_zone" = subnet.availability_zone
      "cidr_block"        = subnet.cidr_block
    }
  }
}

output "has_igw" {
  value = !(var.existing_igw == null && var.existing_vpc == null && var.igw_name == "")
}

output "igw_id" {
  value = local.igw_id
}

output "security_group" {
  value = merge(
    {
      for secgrp in aws_security_group.secgrp :
      secgrp.name => {
        prefix_name = secgrp.name
        id          = secgrp.id
      }
    },
    {
      for secgrp in data.aws_security_group.secgrp :
      secgrp.name => {
        prefix_name = "${var.module_prefix}${secgrp.name}"
        id          = secgrp.id
      }
    }
  )
}
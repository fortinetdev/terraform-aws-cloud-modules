output "vpc_id" {
  value = local.vpc_id
}

output "subnets" {
  value = {
    for subnet in aws_subnet.subnets :
    subnet.tags.Name => {
      "id"                = subnet.id
      "availability_zone" = subnet.availability_zone
    }
  }
}

output "igw" {
  value = local.igw
}

output "security_group" {
  value = {
    for secgrp in aws_security_group.secgrp :
    secgrp.name => secgrp.id
  }
}
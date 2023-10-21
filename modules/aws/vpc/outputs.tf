output "vpc_id" {
  value = local.vpc_id
}

output "subnets" {
  value = {
    for subnet in aws_subnet.subnets :
    subnet.tags.Name => subnet.id
  }
}

output "igw" {
  value = aws_internet_gateway.igw[0].id
}

output "security_group" {
  value = {
    for secgrp in aws_security_group.secgrp :
    secgrp.name => secgrp.id
  }
}
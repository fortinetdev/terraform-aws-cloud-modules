output "route_table" {
  value = local.rt_id
}

output "routes" {
  value = {
    for rt_name, rt_value in aws_route.routes :
    rt_name => rt_value.id
  }
}

output "rt_association" {
  value = {
    "Subnet_associations" = {
      for a_name, a_value in aws_route_table_association.rt_a_subnets :
      a_name => a_value.id
    },
    "Gateway_associations" = {
      for a_name, a_value in aws_route_table_association.rt_a_gateways :
      a_name => a_value.id
    }
  }
}
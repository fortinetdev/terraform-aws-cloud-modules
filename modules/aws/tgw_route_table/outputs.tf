output "tgw_rt_id" {
  value = local.tgw_rt_id
}

output "tgw_routes" {
  value = {
    for r_name, r_value in aws_ec2_transit_gateway_route.tgw_routes :
    r_name => r_value.id
  }
}


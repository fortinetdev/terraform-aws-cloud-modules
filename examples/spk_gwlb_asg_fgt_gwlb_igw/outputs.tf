output "gwlb_ips" {
  value = <<-EOF
  # GWLB IPs: <subnet_id> = <ip>
  # ${"\t"}${join(", \n\t", [for k, v in module.security-vpc-gwlb.gwlb_ips : "${k} = ${v}"])}
  EOF
}

output "secvpc-output" {
  value = {
    "vpc_id"  = module.security-vpc.vpc_id
    "subnets" = module.security-vpc.subnets
  }
}

output "subnets" {
  value = local.subnets
}

output "route_tables" {
  value = local.route_tables
}

output "gwlb_endps" {
  value = local.gwlb_endps
}

output "spkvpc_rt" {
  value = local.spkvpc_rt
}

output "az_name_map" {
  value = local.az_name_map
}
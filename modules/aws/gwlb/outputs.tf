output "gwlb" {
  value = local.gwlb
}

output "gwlb_tgp" {
  value = local.gwlb_tgp
}

output "gwlb_ips" {
  value = {
    for intf_id, intf in data.aws_network_interface.gwlb_intfs :
    intf.subnet_id => intf.private_ip
  }
}

output "gwlb_endps" {
  value = {
    for ep_name, ep_value in aws_vpc_endpoint.gwlb_endps :
    ep_name => ep_value.id
  }
}
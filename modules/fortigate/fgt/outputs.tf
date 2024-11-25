output "fgt_instance" {
  value = aws_instance.fgt
}

output "fgt_public_ip" {
  value = aws_instance.fgt.public_ip
}

output "fgt_public_ips" {
  value = { for k, v in aws_eip.fgt_eips : k => v.public_ip }
}

output "fgt_private_ips" {
  value = { for k, v in aws_network_interface.fgt_intfs : "${var.module_prefix}${k}" => v.private_ip }
}

output "fgt_interface_ids" {
  value = { for k, v in aws_network_interface.fgt_intfs : "${var.module_prefix}${k}" => v.id }
}


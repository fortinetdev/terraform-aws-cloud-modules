output "subnets" {
  value = local.subnets
}

output "security_group" {
  value = module.security-vpc.security_group
}

output "fgts_public_ip" {
  value = { for k, v in module.fgts : k => v.fgt_public_ip }
}
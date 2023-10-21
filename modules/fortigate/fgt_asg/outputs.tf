output "asg_group" {
  value = aws_autoscaling_group.fgt-asg
}

output "lic_s3_name" {
  value = local.lic_s3_name
}

output "asg_policy_list" {
  value = {
    for policy_name, policy_content in aws_autoscaling_policy.scale_policy :
    policy_name => policy_content
  }
}

output "dynamodb_table_name" {
  value = local.dynamodb_table_name
}
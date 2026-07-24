output "hostinger_vps_ip" {
  description = "Target Hostinger VPS Public Address"
  value       = var.hostinger_ip
}

output "deployment_status" {
  description = "Deployment Completion Message"
  value       = "ElevateIQ is running live on https://${var.domain_name}"
}

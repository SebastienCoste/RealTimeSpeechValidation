# TruthSeeker AWS Deployment

This directory contains all the necessary files to deploy TruthSeeker to AWS with a cost-optimized infrastructure.

## Architecture Overview

- **Frontend**: React PWA hosted on S3 + CloudFront
- **Backend**: FastAPI on Fargate (cost-optimized with FARGATE_SPOT)
- **Database**: AWS DocumentDB (MongoDB-compatible)
- **Load Balancer**: Application Load Balancer
- **Container Registry**: ECR
- **Estimated Cost**: ~$83/month

## Prerequisites

1. **AWS CLI** installed and configured
2. **Docker** installed
3. **Node.js/yarn** for frontend build
4. **API Keys**:
   - Perplexity API key
   - OpenAI API key

## Quick Deploy

```bash
cd deploy
chmod +x deploy.sh
./deploy.sh
```

The script will:
1. Build the frontend
2. Build and push the Docker image to ECR
3. Deploy the infrastructure using CloudFormation
4. Upload the frontend to S3
5. Provide you with the URLs

## Manual Deployment Steps

### 1. Build Frontend
```bash
cd frontend
yarn install
yarn build
```

### 2. Build Docker Image
```bash
cd deploy
docker build -f Dockerfile -t truthseeker:latest ..
```

### 3. Deploy Infrastructure
```bash
aws cloudformation deploy \
    --template-file aws-infrastructure.yml \
    --stack-name TruthSeeker-Stack \
    --parameter-overrides \
        Environment=prod \
        PerplexityApiKey=your_key_here \
        OpenAIApiKey=your_key_here \
    --capabilities CAPABILITY_IAM \
    --region us-east-1
```

### 4. Push Image to ECR
```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag truthseeker:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/truthseeker:latest
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/truthseeker:latest
```

### 5. Upload Frontend to S3
```bash
aws s3 sync frontend/build/ s3://your-frontend-bucket/ --delete
```

## Infrastructure Components

### Cost-Optimized Features
- **Fargate SPOT instances** (up to 70% cost savings)
- **Single Fargate task** (can scale up if needed)
- **t3.medium DocumentDB** (right-sized for the workload)
- **CloudFront PriceClass_100** (cheaper edge locations)
- **7-day log retention** (reduced storage costs)

### Scaling Considerations
- **Auto Scaling**: Can be enabled on the ECS service
- **Database**: Can add read replicas if needed
- **CDN**: Global distribution via CloudFront
- **Availability**: Multi-AZ deployment for high availability

## Cost Breakdown (Monthly Estimates)

| Service | Configuration | Cost |
|---------|--------------|------|
| Fargate | 512 CPU, 1GB RAM, SPOT | ~$15 |
| DocumentDB | t3.medium instance | ~$50 |
| ALB | Standard load balancer | ~$16 |
| S3 | Frontend hosting | ~$1 |
| CloudFront | CDN distribution | ~$1 |
| **Total** | | **~$83** |

## URLs After Deployment

- **Individual TruthSeeker**: `https://your-cloudfront-domain.com/`
- **YouTube Live**: `https://your-cloudfront-domain.com/youtube-live`
- **Admin Panel**: `https://your-cloudfront-domain.com/admin`

## Environment Variables

The deployment automatically configures:
- `MONGO_URL`: DocumentDB connection string
- `PERPLEXITY_API_KEY`: Your Perplexity API key
- `OPENAI_API_KEY`: Your OpenAI API key
- `DB_NAME`: Database name (truthseeker)

## Monitoring and Logs

- **CloudWatch Logs**: `/ecs/TruthSeeker-prod`
- **Health Checks**: Configured on `/api/health`
- **Metrics**: Available in CloudWatch

## Security Features

- **VPC**: Isolated network environment
- **Security Groups**: Minimal access rules
- **Secrets Manager**: Secure password storage
- **IAM Roles**: Least privilege access
- **SSL/TLS**: Enforced via CloudFront

## Cleanup

To remove all resources:
```bash
aws cloudformation delete-stack --stack-name TruthSeeker-Stack --region us-east-1
```

## Troubleshooting

### Common Issues

1. **ECS Task Won't Start**
   - Check CloudWatch logs in `/ecs/TruthSeeker-prod`
   - Verify environment variables
   - Check security group rules

2. **Frontend Not Loading**
   - Verify S3 bucket policy
   - Check CloudFront distribution
   - Ensure build files were uploaded

3. **Database Connection Issues**
   - Verify DocumentDB security group
   - Check connection string format
   - Ensure secrets are properly configured

### Useful Commands

```bash
# Check ECS service status
aws ecs describe-services --cluster TruthSeeker-prod --services TruthSeeker-Service-prod

# View logs
aws logs tail /ecs/TruthSeeker-prod --follow

# Check stack status
aws cloudformation describe-stacks --stack-name TruthSeeker-Stack
```

## Next Steps

After deployment:
1. Test all three applications (Individual, YouTube Live, Admin)
2. Configure your domain name (optional)
3. Set up monitoring alerts
4. Configure backup policies
5. Test auto-scaling behavior

## Support

For issues with the deployment:
1. Check CloudWatch logs
2. Verify all prerequisites are met
3. Ensure API keys are valid
4. Check AWS service limits in your region
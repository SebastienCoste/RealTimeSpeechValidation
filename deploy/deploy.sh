#!/bin/bash

# TruthSeeker AWS Deployment Script
# This script deploys the TruthSeeker application to AWS using minimal cost infrastructure

set -e

# Configuration
STACK_NAME="TruthSeeker-Stack"
ENVIRONMENT="prod"
AWS_REGION="us-east-1"  # Cheapest region for most services
PROFILE_NAME="default"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity --profile $PROFILE_NAME &> /dev/null; then
        log_error "AWS credentials not configured or invalid."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Get API keys from user
get_api_keys() {
    log_info "Getting API keys..."
    
    if [ -z "$PERPLEXITY_API_KEY" ]; then
        echo -n "Enter your Perplexity API key: "
        read -s PERPLEXITY_API_KEY
        echo
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        echo -n "Enter your OpenAI API key: "
        read -s OPENAI_API_KEY
        echo
    fi
    
    if [ -z "$PERPLEXITY_API_KEY" ] || [ -z "$OPENAI_API_KEY" ]; then
        log_error "Both API keys are required"
        exit 1
    fi
    
    log_success "API keys collected"
}

# Build and push Docker image
build_and_push_image() {
    log_info "Building and pushing Docker image..."
    
    # Get account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --profile $PROFILE_NAME --query Account --output text)
    ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    
    # Create ECR repository if it doesn't exist
    aws ecr describe-repositories --repository-names truthseeker --region $AWS_REGION --profile $PROFILE_NAME || \
    aws ecr create-repository --repository-name truthseeker --region $AWS_REGION --profile $PROFILE_NAME
    
    # Login to ECR
    aws ecr get-login-password --region $AWS_REGION --profile $PROFILE_NAME | \
    docker login --username AWS --password-stdin $ECR_URI
    
    # Build image
    cd ..
    docker build -f deploy/Dockerfile -t truthseeker:latest .
    
    # Tag and push
    docker tag truthseeker:latest $ECR_URI/truthseeker:latest
    docker push $ECR_URI/truthseeker:latest
    
    cd deploy
    log_success "Docker image built and pushed"
}

# Build frontend
build_frontend() {
    log_info "Building frontend..."
    
    cd ../frontend
    
    # Install dependencies
    if ! command -v yarn &> /dev/null; then
        npm install
        npm run build
    else
        yarn install
        yarn build
    fi
    
    cd ../deploy
    log_success "Frontend built successfully"
}

# Deploy CloudFormation stack
deploy_infrastructure() {
    log_info "Deploying infrastructure..."
    
    aws cloudformation deploy \
        --template-file aws-infrastructure.yml \
        --stack-name $STACK_NAME \
        --parameter-overrides \
            Environment=$ENVIRONMENT \
            PerplexityApiKey=$PERPLEXITY_API_KEY \
            OpenAIApiKey=$OPENAI_API_KEY \
        --capabilities CAPABILITY_IAM \
        --region $AWS_REGION \
        --profile $PROFILE_NAME
    
    log_success "Infrastructure deployed successfully"
}

# Upload frontend to S3
upload_frontend() {
    log_info "Uploading frontend to S3..."
    
    # Get S3 bucket name from CloudFormation output
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucket`].OutputValue' \
        --output text \
        --region $AWS_REGION \
        --profile $PROFILE_NAME)
    
    # Upload files
    aws s3 sync ../frontend/build/ s3://$BUCKET_NAME/ \
        --delete \
        --region $AWS_REGION \
        --profile $PROFILE_NAME
    
    log_success "Frontend uploaded to S3"
}

# Invalidate CloudFront cache
invalidate_cloudfront() {
    log_info "Invalidating CloudFront cache..."
    
    # Get CloudFront distribution ID
    DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
        --output text \
        --region $AWS_REGION \
        --profile $PROFILE_NAME)
    
    if [ "$DISTRIBUTION_ID" != "None" ] && [ -n "$DISTRIBUTION_ID" ]; then
        aws cloudfront create-invalidation \
            --distribution-id $DISTRIBUTION_ID \
            --paths "/*" \
            --region $AWS_REGION \
            --profile $PROFILE_NAME > /dev/null
        
        log_success "CloudFront cache invalidated"
    else
        log_warning "CloudFront distribution not found, skipping cache invalidation"
    fi
}

# Get deployment outputs
show_outputs() {
    log_info "Deployment completed successfully!"
    echo
    log_info "=== Deployment Information ==="
    
    # Get outputs
    FRONTEND_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`FrontendURL`].OutputValue' \
        --output text \
        --region $AWS_REGION \
        --profile $PROFILE_NAME)
    
    BACKEND_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`BackendURL`].OutputValue' \
        --output text \
        --region $AWS_REGION \
        --profile $PROFILE_NAME)
    
    echo -e "${GREEN}Frontend URL:${NC} $FRONTEND_URL"
    echo -e "${GREEN}Backend URL:${NC} $BACKEND_URL"
    echo
    log_info "Individual TruthSeeker: $FRONTEND_URL"
    log_info "YouTube Live Fact-Checker: $FRONTEND_URL/youtube-live"
    log_info "Admin Panel: $FRONTEND_URL/admin"
    echo
    log_info "Estimated monthly cost: ~$83 USD"
    echo
    log_success "TruthSeeker is now live!"
}

# Cleanup function
cleanup() {
    if [ $? -ne 0 ]; then
        log_error "Deployment failed!"
        echo
        log_info "To clean up resources, run:"
        echo "aws cloudformation delete-stack --stack-name $STACK_NAME --region $AWS_REGION --profile $PROFILE_NAME"
    fi
}

# Main deployment function
main() {
    log_info "Starting TruthSeeker deployment..."
    echo
    
    # Set up cleanup trap
    trap cleanup EXIT
    
    # Run deployment steps
    check_prerequisites
    get_api_keys
    build_frontend
    build_and_push_image
    deploy_infrastructure
    upload_frontend
    invalidate_cloudfront
    show_outputs
}

# Run main function
main "$@"
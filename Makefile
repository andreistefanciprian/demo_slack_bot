# Define variables
IMAGE_NAME := andreistefanciprian/watchlist-slack-bot
TAG := latest

# Docker build and push commands
build:
	docker build -t $(IMAGE_NAME):$(TAG) . -f infra/Dockerfile

push: build
	docker push $(IMAGE_NAME):$(TAG)

# Phony targets to avoid filename conflicts
.PHONY: build push

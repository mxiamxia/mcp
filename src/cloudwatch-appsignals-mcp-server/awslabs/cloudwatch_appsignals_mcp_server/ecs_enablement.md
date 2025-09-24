# Enable AWS Application Signals for ECS Services - Complete Implementation Guide

## Overview
This guide provides complete steps to enable AWS Application Signals for ECS Fargate services, enabling automatic service discovery, distributed tracing, performance monitoring, and service mapping.

## Prerequisites
- Services running on ECS both the ec2 and Fargate launch types.
- Applications using supported languages (Python, Java, .NET, Node.js)

## Implementation Steps

**Constraints:**
You must strictly follow the steps in the order below, do not skip or combine steps.

### Step 1: Enable Application Signals Discovery

First, enable Application Signals service discovery in your stack:

```typescript
// Import Application Signals module
import * as applicationsignals from 'aws-cdk-lib/aws-applicationsignals';

// Add in stack constructor
const cfnDiscovery = new applicationsignals.CfnDiscovery(this,
  'ApplicationSignalsDiscovery', { }
);
```

### Step 2: Add CloudWatch Agent Permissions to ECS Task Role

Update ECS task role to add CloudWatchAgentServerPolicy:

```typescript
// Update existing taskRole or create new one
const taskRole = new iam.Role(this, 'EcsTaskRole', {
  assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
  managedPolicies: [
    iam.ManagedPolicy.fromAwsManagedPolicyName('AWSXRayDaemonWriteAccess'),
    iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchAgentServerPolicy'), // Add this policy
  ],
  inlinePolicies: {
    // Your existing inline policies...
  },
});
```

### Step 3: Setup CloudWatch Agent Task

#### 3.1 Import Required Modules
```typescript
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
```

#### 3.2 Create CloudWatch Agent Configuration Secret
```typescript
const cwAgentConfigSecret = new secretsmanager.Secret(this, 'CwAgentConfigSecret', {
  secretName: 'ecs-cwagent',
  description: 'CloudWatch Agent configuration for ECS services',
  secretStringValue: cdk.SecretValue.unsafePlainText(JSON.stringify({
    "traces": {
      "traces_collected": {
        "application_signals": {}
      }
    },
    "logs": {
      "metrics_collected": {
        "application_signals": {}
      }
    }
  })),
  removalPolicy: cdk.RemovalPolicy.DESTROY,
});
```

#### 3.3 Create CloudWatch Agent Log Group
```typescript
const cwAgentLogGroup = new logs.LogGroup(this, 'CwAgentLogGroup', {
  logGroupName: '/ecs/ecs-cwagent',
  removalPolicy: cdk.RemovalPolicy.DESTROY,
  retention: logs.RetentionDays.ONE_WEEK,
});
```

#### 3.4 Update Task Execution Role Permissions
```typescript
// Grant task execution role permission to read secret
cwAgentConfigSecret.grantRead(taskExecutionRole);
```

#### 3.5 Add CloudWatch Agent Container to Each Task Definition
```typescript
// Add CloudWatch Agent sidecar to each task definition
const cwAgentContainer = taskDefinition.addContainer('ecs-cwagent-{SERVICE_NAME}', {
  image: ecs.ContainerImage.fromRegistry('public.ecr.aws/cloudwatch-agent/cloudwatch-agent:latest'),
  essential: false,
  memoryReservationMiB: 128,
  cpu: 64,
  secrets: {
    CW_CONFIG_CONTENT: ecs.Secret.fromSecretsManager(cwAgentConfigSecret),
  },
  logging: ecs.LogDrivers.awsLogs({
    streamPrefix: 'ecs',
    logGroup: cwAgentLogGroup,
  }),
});
```

### Step 4: Add ADOT Zero-Code Instrumentation to Main Service

#### 4.1 Add Bind Mount Volumes to Task Definition
```typescript
const taskDefinition = new ecs.FargateTaskDefinition(this, '{SERVICE_NAME}TaskDefinition', {
  // Existing configuration...
  volumes: [
    {
      name: "opentelemetry-auto-instrumentation-python" // Adjust name based on language
    }
  ],
});
```

#### 4.2 Add ADOT Auto-instrumentation Init Container
```typescript
// Choose appropriate image based on application language:
// - Python: public.ecr.aws/aws-observability/adot-autoinstrumentation-python:v0.12.0
// - Java: public.ecr.aws/aws-observability/adot-autoinstrumentation-java:v2.11.4
// - .NET: public.ecr.aws/aws-observability/adot-autoinstrumentation-dotnet:v1.9.0
// - Node.js: public.ecr.aws/aws-observability/adot-autoinstrumentation-node:v0.7.0

const initContainer = taskDefinition.addContainer('init', {
  image: ecs.ContainerImage.fromRegistry('public.ecr.aws/aws-observability/adot-autoinstrumentation-python:v0.12.0'),
  essential: false,
  memoryReservationMiB: 64,
  cpu: 32,
  // Python, .Net, Node.js
  command: ['cp', '-a', '/autoinstrumentation/.', '/otel-auto-instrumentation-python/'],
  // Java
  // command: ['cp', '-a', '/javaagent/.', '/otel-auto-instrumentation/javaagent.jar'],

  logging: ecs.LogDrivers.awsLogs({
    streamPrefix: 'init-{SERVICE_NAME}',
    logGroup: serviceLogGroup,
  }),
});

// Add mount point to init container
initContainer.addMountPoints({
  sourceVolume: 'opentelemetry-auto-instrumentation-python',
  containerPath: '/otel-auto-instrumentation-python',
  readOnly: false,
});
```

#### 4.3 Configure Main Application Container OpenTelemetry Environment Variables

##### Python Application Configuration:
```typescript
const mainContainer = taskDefinition.addContainer('{SERVICE_NAME}-container', {
  // Existing configuration...
  environment: {
    // Existing environment variables...

    // ADOT Configuration for Application Signals
    OTEL_RESOURCE_ATTRIBUTES: 'service.name={SERVICE_NAME},deployment.environment=ecs-fargate,team.name={TEAM_NAME},business.unit={BUSINESS_UNIT},app={APP_NAME}',
    OTEL_METRICS_EXPORTER: 'none',
    OTEL_LOGS_EXPORTER: 'none',
    PYTHONPATH: '/otel-auto-instrumentation-python/opentelemetry/instrumentation/auto_instrumentation:/otel-auto-instrumentation-python',
    OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED: 'true',
    OTEL_TRACES_EXPORTER: 'otlp',
    OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
    OTEL_PYTHON_DISTRO: 'aws_distro',
    OTEL_PYTHON_CONFIGURATOR: 'aws_configurator',
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: 'http://localhost:4316/v1/traces',
    OTEL_AWS_APPLICATION_SIGNALS_EXPORTER_ENDPOINT: 'http://localhost:4316/v1/metrics',
    OTEL_AWS_APPLICATION_SIGNALS_ENABLED: 'true',
  },
});
```

##### Java Application Configuration:
```typescript
environment: {
  // Existing environment variables...
  OTEL_RESOURCE_ATTRIBUTES: 'service.name={SERVICE_NAME},deployment.environment=ecs-fargate',
  OTEL_METRICS_EXPORTER: 'none',
  OTEL_LOGS_EXPORTER: 'none',
  OTEL_TRACES_EXPORTER: 'otlp',
  OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
  OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: 'http://localhost:4316/v1/traces',
  OTEL_AWS_APPLICATION_SIGNALS_EXPORTER_ENDPOINT: 'http://localhost:4316/v1/metrics',
  OTEL_AWS_APPLICATION_SIGNALS_ENABLED: 'true',
  JAVA_TOOL_OPTIONS: '-javaagent:/otel-auto-instrumentation-java/javaagent.jar',
}
```

##### Node.js Application Configuration:
```typescript
environment: {
  // Existing environment variables...
  OTEL_RESOURCE_ATTRIBUTES: 'service.name={SERVICE_NAME},deployment.environment=ecs-fargate',
  OTEL_METRICS_EXPORTER: 'none',
  OTEL_LOGS_EXPORTER: 'none',
  OTEL_TRACES_EXPORTER: 'otlp',
  OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
  OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: 'http://localhost:4316/v1/traces',
  OTEL_AWS_APPLICATION_SIGNALS_EXPORTER_ENDPOINT: 'http://localhost:4316/v1/metrics',
  OTEL_AWS_APPLICATION_SIGNALS_ENABLED: 'true',
  NODE_OPTIONS: '--require /otel-auto-instrumentation-node/autoinstrumentation.js',
}
```

#### 4.4 Add Mount Point to Main Container
```typescript
// Add mount point to main application container
mainContainer.addMountPoints({
  sourceVolume: 'opentelemetry-auto-instrumentation-python', // Adjust based on language
  containerPath: '/otel-auto-instrumentation-python', // Adjust based on language
  readOnly: false,
});
```

#### 4.5 Configure Container Dependencies
```typescript
// Ensure containers start in correct order
mainContainer.addContainerDependencies({
  container: initContainer,
  condition: ecs.ContainerDependencyCondition.SUCCESS,
});

mainContainer.addContainerDependencies({
  container: cwAgentContainer,
  condition: ecs.ContainerDependencyCondition.START,
});
```

## Complete Example Template

```typescript
import * as cdk from 'aws-cdk-lib';
import * as applicationsignals from 'aws-cdk-lib/aws-applicationsignals';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';

export class MyServiceStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Step 1: Enable Application Signals Discovery
    const cfnDiscovery = new applicationsignals.CfnDiscovery(this, 'ApplicationSignalsDiscovery', {});

    // Step 3: Create CloudWatch Agent configuration
    const cwAgentConfigSecret = new secretsmanager.Secret(this, 'CwAgentConfigSecret', {
      secretName: 'ecs-cwagent',
      description: 'CloudWatch Agent configuration for ECS services',
      secretStringValue: cdk.SecretValue.unsafePlainText(JSON.stringify({
        "traces": { "traces_collected": { "application_signals": {} } },
        "logs": { "metrics_collected": { "application_signals": {} } }
      })),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const cwAgentLogGroup = new logs.LogGroup(this, 'CwAgentLogGroup', {
      logGroupName: '/ecs/ecs-cwagent',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      retention: logs.RetentionDays.ONE_WEEK,
    });

    // Task roles with required permissions
    const taskExecutionRole = new iam.Role(this, 'TaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
      ],
    });

    cwAgentConfigSecret.grantRead(taskExecutionRole);

    // Step 2: Task Role with CloudWatch Agent permissions
    const taskRole = new iam.Role(this, 'EcsTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AWSXRayDaemonWriteAccess'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchAgentServerPolicy'),
      ],
    });

    // Step 4: Task Definition with volumes
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'MyServiceTaskDefinition', {
      memoryLimitMiB: 512,
      cpu: 256,
      executionRole: taskExecutionRole,
      taskRole: taskRole,
      volumes: [{ name: "opentelemetry-auto-instrumentation-python" }],
    });

    // CloudWatch Agent sidecar
    const cwAgentContainer = taskDefinition.addContainer('ecs-cwagent', {
      image: ecs.ContainerImage.fromRegistry('public.ecr.aws/cloudwatch-agent/cloudwatch-agent:latest'),
      essential: false,
      memoryReservationMiB: 128,
      cpu: 64,
      secrets: { CW_CONFIG_CONTENT: ecs.Secret.fromSecretsManager(cwAgentConfigSecret) },
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: 'ecs', logGroup: cwAgentLogGroup }),
    });

    // ADOT init container
    const initContainer = taskDefinition.addContainer('init', {
      image: ecs.ContainerImage.fromRegistry('public.ecr.aws/aws-observability/adot-autoinstrumentation-python:v0.12.0'),
      essential: false,
      memoryReservationMiB: 64,
      cpu: 32,
      command: ['cp', '-a', '/autoinstrumentation/.', '/otel-auto-instrumentation-python/'],
    });

    initContainer.addMountPoints({
      sourceVolume: 'opentelemetry-auto-instrumentation-python',
      containerPath: '/otel-auto-instrumentation-python',
      readOnly: false,
    });

    // Main application container with OTEL configuration
    const mainContainer = taskDefinition.addContainer('my-service-container', {
      image: ecs.ContainerImage.fromAsset('./my-service'),
      environment: {
        // Application-specific environment variables...

        // ADOT Configuration for Application Signals
        OTEL_RESOURCE_ATTRIBUTES: 'service.name=my-service,deployment.environment=ecs-fargate',
        OTEL_METRICS_EXPORTER: 'none',
        OTEL_LOGS_EXPORTER: 'none',
        PYTHONPATH: '/otel-auto-instrumentation-python/opentelemetry/instrumentation/auto_instrumentation:/otel-auto-instrumentation-python',
        OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED: 'true',
        OTEL_TRACES_EXPORTER: 'otlp',
        OTEL_EXPORTER_OTLP_PROTOCOL: 'http/protobuf',
        OTEL_PYTHON_DISTRO: 'aws_distro',
        OTEL_PYTHON_CONFIGURATOR: 'aws_configurator',
        OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: 'http://localhost:4316/v1/traces',
        OTEL_AWS_APPLICATION_SIGNALS_EXPORTER_ENDPOINT: 'http://localhost:4316/v1/metrics',
        OTEL_AWS_APPLICATION_SIGNALS_ENABLED: 'true',
      },
    });

    mainContainer.addMountPoints({
      sourceVolume: 'opentelemetry-auto-instrumentation-python',
      containerPath: '/otel-auto-instrumentation-python',
      readOnly: false,
    });

    // Configure container dependencies
    mainContainer.addContainerDependencies({
      container: initContainer,
      condition: ecs.ContainerDependencyCondition.SUCCESS,
    });

    mainContainer.addContainerDependencies({
      container: cwAgentContainer,
      condition: ecs.ContainerDependencyCondition.START,
    });

    // Create ECS Service...
  }
}
```

## Language-Specific Configuration Reference

### Supported Auto-instrumentation Images
- **Python**: `public.ecr.aws/aws-observability/adot-autoinstrumentation-python:v0.12.0`
- **Java**: `public.ecr.aws/aws-observability/adot-autoinstrumentation-java:v2.11.4`
- **Node.js**: `public.ecr.aws/aws-observability/adot-autoinstrumentation-node:v0.7.0`
- **.NET**: `public.ecr.aws/aws-observability/adot-autoinstrumentation-dotnet:v1.9.0`

### Container Paths and Environment Variables
- **Python**: Path `/otel-auto-instrumentation-python`, requires `PYTHONPATH`
- **Java**: Path `/otel-auto-instrumentation-java`, requires `JAVA_TOOL_OPTIONS`
- **Node.js**: Path `/otel-auto-instrumentation-node`, requires `NODE_OPTIONS`
- **.NET**: Path `/otel-auto-instrumentation-dotnet`, requires corresponding .NET configuration

## Verification and Monitoring

1. **After deploying services**, generate some traffic to your applications
2. **Check CloudWatch Application Signals console**:
   - Navigate to CloudWatch → Application Signals → Services
   - Verify services appear in the service map
   - Check that metrics and traces are being collected

3. **Common endpoints**:
   - Traces: `http://localhost:4316/v1/traces`
   - Metrics: `http://localhost:4316/v1/metrics`
   - CloudWatch Agent configuration provided via Secrets Manager

## Troubleshooting

1. **Service not appearing in Application Signals**:
   - Check CloudWatch Agent logs
   - Verify environment variables are set correctly
   - Ensure Application Signals is enabled in your account

2. **Container startup failures**:
   - Check container dependency configuration
   - Verify IAM permissions
   - Check mount points configuration

3. **Missing trace data**:
   - Verify OTLP endpoint accessibility
   - Check application logs for OpenTelemetry initialization information
   - Ensure auto-instrumentation libraries are loaded correctly

## Important Notes

- This instruction is for ECS both the ec2 and Fargate launch types.
- Ensures application code requires no modifications (zero-code instrumentation)
- CloudWatch Agent and ADOT collector run as sidecar containers
- All configuration provided via environment variables and mount points
- Supports custom service attributes and tags for categorization and filtering

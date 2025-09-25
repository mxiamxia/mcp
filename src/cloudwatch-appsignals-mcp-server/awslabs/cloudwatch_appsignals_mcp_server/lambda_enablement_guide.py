# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Lambda enablement guide content as a Python string constant.

This eliminates file path issues when reading the guide content.
"""

LAMBDA_ENABLEMENT_GUIDE = """# AWS Application Signals for Lambda Functions - Configuration Guide

This guide provides complete steps to enable AWS Application Signals for Lambda functions, enhancing your project's observability.

## Overview

AWS Application Signals is AWS's monitoring product that automatically provides application-level telemetry data for Lambda functions, including:
- Distributed tracing
- Application metrics
- Service dependency maps
- SLO monitoring
- Error analysis

## Configuration Steps
**Constraints:**
You must strictly follow the steps in the order below, do not skip or combine steps.

### Step 1: Enable AWS Application Signals Discovery

Add Application Signals Discovery configuration in your CDK Stack:


**Reference Implementation (CDK):**
```typescript
import * as applicationsignals from 'aws-cdk-lib/aws-applicationsignals';

// Add this in your Stack constructor
const cfnDiscovery = new applicationsignals.CfnDiscovery(this,
  'ApplicationSignalsDiscovery', { }
);
```

### Step 2: Get ADOT Lambda Layer ARN

**Constraints:**
Get the ADOT Lambda Layer ARNs from AWS guide https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Application-Signals-Enable-LambdaMain.html#Enable-Lambda-Layers

1. Visit AWS official documentation: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Application-Signals-Enable-LambdaMain.html#Enable-Lambda-Layers, get all Lambda layer ARNs and put them into a map 'layerArns'

2. Select the correct Layer ARN based on your runtime and region


**Reference Implementation (CDK):**
```typescript
// ADOT Lambda Layer for Application Signals
const adotLayerArn = (() => {
  const layerArns: { [key: string]: string } = {
    // Getting actual ARNs from https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Application-Signals-Enable-LambdaMain.html#Enable-Lambda-Layers
    'us-east-1': 'arn:aws:lambda:us-east-1:615299751070:layer:AWSOpenTelemetryDistroPython:16',
    'us-east-2': 'arn:aws:lambda:us-east-2:615299751070:layer:AWSOpenTelemetryDistroPython:13',
    'us-west-1': 'arn:aws:lambda:us-west-1:615299751070:layer:AWSOpenTelemetryDistroPython:20',
    'us-west-2': 'arn:aws:lambda:us-west-2:615299751070:layer:AWSOpenTelemetryDistroPython:20',
    'eu-west-1': 'arn:aws:lambda:eu-west-1:615299751070:layer:AWSOpenTelemetryDistroPython:13',
    ... ...
  };
  return layerArns[this.region] || layerArns['us-east-1']; // Fallback to us-east-1
})();

const adotLayer = lambda.LayerVersion.fromLayerVersionArn(
  this, 'AwsLambdaLayerForOtel',
  adotLayerArn
);
```

**Note:**
- Select the correct Layer arn based on region and Lambda runtime(Python/Js/Java/DotNet)

### Step 3: Configure IAM Permissions

Add Application Signals execution permissions for each Lambda function:


**Reference Implementation (CDK):**
```typescript
// Add AWS managed policy to Lambda function
lambdaFunction.role?.addManagedPolicy(
  iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchLambdaApplicationSignalsExecutionRolePolicy')
);
```

### Step 4: Enable Lambda Active Tracing

Enable Active tracing for each Lambda function:


**Reference Implementation (CDK):**
```typescript
const lambdaFunction = new lambda.Function(this, 'MyFunction', {
  // Other configurations...
  tracing: lambda.Tracing.ACTIVE,
  // Other configurations...
});
```

### Step 5: Add ADOT Lambda Layer to Lambda

Configure AWS Lambda Layer in Lambda:


**Reference Implementation (CDK):**
```typescript
// Lambda Function - Card Verification Service
  const lambdaFunction = new lambda.Function(this, 'lambdaFunction', {
    functionName: 'lambdaFunction',
    runtime: lambda.Runtime.PYTHON_3_11,
    layers: [adotLayer], // Add ADOT Layer
  });
```

### Step 6: Configure Environment Variables

Add necessary Application Signals environment variables for each Lambda function:

**Reference Implementation (CDK):**
```typescript
const lambdaFunction = new lambda.Function(this, 'MyFunction', {
  // Other configurations...
  environment: {
    // Your other environment variables...
    AWS_LAMBDA_EXEC_WRAPPER: '/opt/otel-instrument', // Required for Application Signals
  },
  // Other configurations...
});
```

### Step 7: Enable OTel Logs (Optional)

**This is an optional step**. If you need to export Lambda function logs through OpenTelemetry, you can enable this feature:

#### Prerequisites:
1. Pre-create custom CloudWatch Log Group and Log Stream
2. Ensure Lambda execution role has permissions to write to these log groups

#### Configure Environment Variables:

**Reference Implementation (CDK):**
```typescript
// Custom Log Group with Custom Log Stream
// Use Custom Resource to conditionally create log group and stream only if they don't exist

// Custom Resource that handles both log group and log stream creation
const logResourceManager = new cr.AwsCustomResource(this, 'LogResourceManager', {
  onUpdate: {
    service: 'CloudWatchLogs',
    action: 'createLogGroup',
    parameters: {
      logGroupName: 'CustomLogGroup',
      retentionInDays: 7
    },
    physicalResourceId: cr.PhysicalResourceId.of('CustomLogGroup'),
    ignoreErrorCodesMatching: 'ResourceAlreadyExistsException',
  },
  onCreate: {
    service: 'CloudWatchLogs',
    action: 'createLogGroup',
    parameters: {
      logGroupName: 'CustomLogGroup',
      retentionInDays: 7
    },
    physicalResourceId: cr.PhysicalResourceId.of('CustomLogGroup'),
    ignoreErrorCodesMatching: 'ResourceAlreadyExistsException',
  },
  onDelete: {
    service: 'CloudWatchLogs',
    action: 'deleteLogGroup',
    parameters: {
      logGroupName: 'CustomLogGroup'
    },
    ignoreErrorCodesMatching: 'ResourceNotFoundException',
  },
  policy: cr.AwsCustomResourcePolicy.fromSdkCalls({
    resources: cr.AwsCustomResourcePolicy.ANY_RESOURCE,
  }),
});

// Custom Resource for log stream creation
const logStreamManager = new cr.AwsCustomResource(this, 'LogStreamManager', {
  onUpdate: {
    service: 'CloudWatchLogs',
    action: 'createLogStream',
    parameters: {
      logGroupName: 'CustomLogGroup',
      logStreamName: 'CustomLogStream'
    },
    physicalResourceId: cr.PhysicalResourceId.of('CustomLogStream'),
    ignoreErrorCodesMatching: 'ResourceAlreadyExistsException',
  },
  onCreate: {
    service: 'CloudWatchLogs',
    action: 'createLogStream',
    parameters: {
      logGroupName: 'CustomLogGroup',
      logStreamName: 'CustomLogStream'
    },
    physicalResourceId: cr.PhysicalResourceId.of('CustomLogStream'),
    ignoreErrorCodesMatching: 'ResourceAlreadyExistsException',
  },
  onDelete: {
    service: 'CloudWatchLogs',
    action: 'deleteLogStream',
    parameters: {
      logGroupName: 'CustomLogGroup',
      logStreamName: 'CustomLogStream'
    },
    ignoreErrorCodesMatching: 'ResourceNotFoundException',
  },
  policy: cr.AwsCustomResourcePolicy.fromSdkCalls({
    resources: cr.AwsCustomResourcePolicy.ANY_RESOURCE,
  }),
});

// Add dependency so log stream is created after log group
logStreamManager.node.addDependency(logResourceManager);

// Reference the log group for other uses in the stack
const customLogGroup = logs.LogGroup.fromLogGroupName(this, 'CustomLogGroupRef', 'CustomLogGroup');


const lambdaFunction = new lambda.Function(this, 'MyFunction', {
  // Other configurations...
  environment: {
    // Your other environment variables...
    AWS_LAMBDA_EXEC_WRAPPER: '/opt/otel-instrument', // Required for Application Signals

    // === Optional: OTel Logs Configuration ===
    OTEL_EXPORTER_OTLP_LOGS_ENDPOINT: `https://logs.${this.region}.amazonaws.com/v1/logs`,
    OTEL_EXPORTER_OTLP_LOGS_HEADERS: "x-aws-log-group=CustomLogGroup,x-aws-log-stream=CustomLogStream",
    OTEL_LOGS_EXPORTER: "otlp",

    // Python Runtime Specific (if using Python)
    OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED: "true",
  },
  // Other configurations...
});
```

**Note:**
- For Python runtime, you need to add `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED: "true"`
- Ensure Lambda execution role has `logs:CreateLogStream` and `logs:PutLogEvents` permissions

#### IAM Permission Requirements (for OTel Logs):

```typescript
// Add necessary IAM permissions for OTel Logs
lambdaFunction.addToRolePolicy(new iam.PolicyStatement({
  actions: [
    'logs:CreateLogStream',
    'logs:PutLogEvents'
  ],
  resources: [
    `arn:aws:logs:${this.region}:${this.account}:log-group:<CustomLogGroup>:*`
  ]
}));
```

## Complete Example

Here's a complete Lambda function configuration example:

```typescript
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as applicationsignals from 'aws-cdk-lib/aws-applicationsignals';

export class MyAppStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Step 1: Enable Application Signals Discovery
    const cfnDiscovery = new applicationsignals.CfnDiscovery(this,
      'ApplicationSignalsDiscovery', { }
    );

    // Step 4: Configure ADOT Layer
    // Get ADOT Lambda layer ARN from AWS documentation: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Application-Signals-Enable-LambdaMain.html#Enable-Lambda-Layers
    const adotLayer = lambda.LayerVersion.fromLayerVersionArn(
      this, 'AwsLambdaLayerForOtel',
    );

    // Create Lambda function
    const myFunction = new lambda.Function(this, 'MyFunction', {
      functionName: 'my-service',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'my_handler.handler',
      code: lambda.Code.fromAsset('lambda/my-service'),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      tracing: lambda.Tracing.ACTIVE, // Step 3: Enable Active tracing
      layers: [adotLayer], // Step 4: Add ADOT Layer
      environment: {
        // Your business environment variables...
        AWS_LAMBDA_EXEC_WRAPPER: '/opt/otel-instrument', // Step 5: Required environment variable

        // === Step 7: Optional OTel Logs Configuration ===
        // If you need to enable OTel Logs, uncomment the lines below and replace placeholders
        // OTEL_EXPORTER_OTLP_LOGS_ENDPOINT: `https://logs.${this.region}.amazonaws.com/v1/logs`,
        // OTEL_EXPORTER_OTLP_LOGS_HEADERS: "x-aws-log-group=my-custom-log-group,x-aws-log-stream=my-custom-log-stream",
        // OTEL_LOGS_EXPORTER: "otlp",
        // OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED: "true", // Python specific
      },
      logGroup: new logs.LogGroup(this, 'MyFunctionLogGroup', {
        logGroupName: '/aws/lambda/my-service',
        retention: logs.RetentionDays.ONE_YEAR,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });

    // Step 3: Add IAM permissions
    myFunction.role?.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName('CloudWatchLambdaApplicationSignalsExecutionRolePolicy')
    );

    // Step 7: Optional OTel Logs IAM permissions (if OTel Logs is enabled)
    // Uncomment the lines below and replace Log Group name
    // myFunction.addToRolePolicy(new iam.PolicyStatement({
    //   actions: [
    //     'logs:CreateLogStream',
    //     'logs:PutLogEvents'
    //   ],
    //   resources: [
    //     `arn:aws:logs:${this.region}:${this.account}:log-group:my-custom-log-group:*`
    //   ]
    // }));
  }
}
```

## Supported Runtimes and Layer ARNs

### Python Runtime
Use `AWSOpenTelemetryDistroPython` layer

### Node.js Runtime
Use `AWSOpenTelemetryDistroJs` layer, replace `Python` with `Js` in the Layer ARN

### Java Runtime
Use `AWSOpenTelemetryDistroJava` layer, replace `Python` with `Java` in the Layer ARN

### .NET Runtime
Use `AWSOpenTelemetryDistroDotNet` layer, replace `Python` with `DotNet` in the Layer ARN

## Getting Latest Layer ARNs

The latest Layer ARNs can be found in the AWS official documentation:
https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Application-Signals-Enable-LambdaMain.html#Enable-Lambda-Layers

## Verification

After configuration, you can verify through the following methods:

1. **CloudWatch Application Signals Console**:
   - Navigate to CloudWatch console
   - Select "Application Signals" > "Services"
   - Confirm your Lambda functions appear in the services list

2. **Check Traces**:
   - Trigger Lambda functions
   - View traces and metrics in Application Signals

3. **Service Map**:
   - View automatically generated service dependency maps in Application Signals

## Important Considerations

1. **Permission Requirements**: Ensure Lambda execution role has necessary Application Signals permissions
2. **Layer Versions**: Regularly update to the latest ADOT Layer versions
3. **Region Support**: Confirm your AWS region supports Application Signals
4. **Cost Considerations**: Application Signals will incur additional CloudWatch costs
5. **Performance Impact**: ADOT Layer will add minimal cold start time

## Troubleshooting

### Common Issues:

1. **Lambda functions don't appear in Application Signals**:
   - Check IAM permission configuration
   - Confirm environment variables are set correctly
   - Verify Layer ARN is correct

2. **Missing Traces**:
   - Confirm Active tracing is enabled
   - Check if Lambda functions are being triggered correctly

3. **Deployment Failures**:
   - Confirm the Layer ARN is available in target region
   - Check CDK version compatibility

## Advanced Configurations

### Custom Service Name
```typescript
environment: {
  OTEL_SERVICE_NAME: 'my-custom-service-name', // Custom service name
  AWS_LAMBDA_EXEC_WRAPPER: '/opt/otel-instrument',
}
```

### Sampling Configuration
```typescript
environment: {
  OTEL_TRACES_SAMPLER: 'traceidratio',
  OTEL_TRACES_SAMPLER_ARG: '0.3', // 30% sampling rate
  AWS_LAMBDA_EXEC_WRAPPER: '/opt/otel-instrument',
}
```

### Enable All Library Instrumentation
```typescript
environment: {
  OTEL_PYTHON_DISABLED_INSTRUMENTATIONS: 'none', // Python
  // OTEL_NODE_DISABLED_INSTRUMENTATIONS: 'none', // Node.js
  // OTEL_INSTRUMENTATION_COMMON_DEFAULT_ENABLED: 'true', // Java
  AWS_LAMBDA_EXEC_WRAPPER: '/opt/otel-instrument',
}
```

## Summary

Through the above five steps, you can successfully enable AWS Application Signals for Lambda functions, gaining:
- Automatic distributed tracing
- Application performance monitoring
- Service dependency visualization
- Error and exception analysis
- SLO/SLI monitoring capabilities

This will significantly enhance your application's observability, helping you quickly identify and resolve issues.
"""

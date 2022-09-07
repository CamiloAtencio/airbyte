/*
 * Copyright (c) 2022 Airbyte, Inc., all rights reserved.
 */

package io.airbyte.workers.config;

import io.airbyte.config.storage.CloudStorageConfigs;
import io.airbyte.workers.ContainerOrchestratorConfig;
import io.airbyte.workers.general.DocumentStoreClient;
import io.airbyte.workers.storage.StateClients;
import io.fabric8.kubernetes.client.DefaultKubernetesClient;
import io.micronaut.context.annotation.Factory;
import io.micronaut.context.annotation.Requires;
import io.micronaut.context.annotation.Value;
import io.micronaut.core.util.StringUtils;
import java.nio.file.Path;
import java.util.Optional;
import javax.inject.Named;
import javax.inject.Singleton;

/**
 * Micronaut bean factory for container orchestrator configuration-related singletons.
 */
@Factory
public class ContainerOrchestratorConfigBeanFactory {

  // IMPORTANT: Changing the storage location will orphan already existing kube pods when the new
  // version is deployed!
  private static final Path STATE_STORAGE_PREFIX = Path.of("/state");

  @Singleton
  @Requires(property = "airbyte.container.orchestrator.enabled",
            value = "true")
  @Named("containerOrchestratorConfig")
  public Optional<ContainerOrchestratorConfig> kubernetesContainerOrchestratorConfig(
                                                                                     @Named("stateStorageConfigs") final CloudStorageConfigs cloudStateStorageConfiguration,
                                                                                     @Value("${airbyte.version}") final String airbyteVersion,
                                                                                     @Value("${airbyte.container.orchestrator.image}") final String containerOrchestratorImage,
                                                                                     @Value("${airbyte.job.kube.main.container.image-pull-policy}") final String containerOrchestratorImagePullPolicy,
                                                                                     @Value("${airbyte.container.orchestrator.secret-mount-path}") final String containerOrchestratorSecretMountPath,
                                                                                     @Value("${airbyte.container.orchestrator.secret-name}") final String containerOrchestratorSecretName,
                                                                                     @Value("${google.application.credentials}") final String googleApplicationCredentials,
                                                                                     @Value("${airbyte.worker.job.kube.namespace}") final String namespace) {
    final var kubernetesClient = new DefaultKubernetesClient();

    final DocumentStoreClient documentStoreClient = StateClients.create(
        cloudStateStorageConfiguration,
        STATE_STORAGE_PREFIX);

    return Optional.of(new ContainerOrchestratorConfig(
        namespace,
        documentStoreClient,
        kubernetesClient,
        containerOrchestratorSecretName,
        containerOrchestratorSecretMountPath,
        StringUtils.isNotEmpty(containerOrchestratorImage) ? containerOrchestratorImage : "airbyte/container-orchestrator:" + airbyteVersion,
        containerOrchestratorImagePullPolicy,
        googleApplicationCredentials));
  }

  @Singleton
  @Requires(property = "airbyte.container.orchestrator.enabled",
            value = "false")
  @Named("containerOrchestratorConfig")
  public Optional<ContainerOrchestratorConfig> defaultContainerOrchestratorConfig() {
    return Optional.empty();
  }

}
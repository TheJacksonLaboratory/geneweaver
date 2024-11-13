import { Environment } from './environment-interface';
import { environment as prodEnvironment } from './environment.jax-cluster-prod-10--prod';

export const environment: Environment = {
  ...prodEnvironment,
  urls: {
    geneWeaver: 'https://geneweaver-stage.jax.org',
  },
};

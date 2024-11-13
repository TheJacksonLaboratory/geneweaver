import { Environment } from './environment-interface';
import { environment as defaultEnvironment } from './environment.jax-cluster-prod-10--prod';

export const environment: Environment = {
  ...defaultEnvironment,
  urls: {
    geneWeaver: 'https://geneweaver-stage.jax.org',
  },
};

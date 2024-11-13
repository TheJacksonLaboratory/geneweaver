import { Environment } from './environment-interface';
import { environment as sqaEnvironment } from './environment.jax-cluster-dev-10--sqa'
import { version } from "./version";

export const environment: Environment = {
  ...sqaEnvironment,
  urls: {
    geneWeaver: 'https://geneweaver-dev.jax.org',
  },
};

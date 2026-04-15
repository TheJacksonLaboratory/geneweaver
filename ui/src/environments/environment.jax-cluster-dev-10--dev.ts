import { Environment } from './environment-interface';
import { environment as sqaEnvironment } from './environment.jax-cluster-dev-10--sqa'

export const environment: Environment = {
  ...sqaEnvironment,
  urls: {
    geneWeaver: 'https://geneweaver-dev.jax.org',
    pubmed: 'https://pubmed.ncbi.nlm.nih.gov',
  },
};

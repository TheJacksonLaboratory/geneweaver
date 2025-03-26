import { Environment } from './environment-interface';
import { environment as defaultEnvironment } from './environment.default';
import { version } from "./version";

export const environment: Environment = {
  ...defaultEnvironment,
  version: version,
  urls: {
    geneWeaver: 'https://geneweaver-sqa.jax.org',
    pubmed: 'https://pubmed.ncbi.nlm.nih.gov',
  },
};

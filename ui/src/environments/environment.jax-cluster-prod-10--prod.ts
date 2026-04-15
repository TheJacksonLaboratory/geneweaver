import { Environment } from './environment-interface';
import { environment as defaultEnvironment } from './environment.default';
import { version } from "./version";

export const environment: Environment = {
  ...defaultEnvironment,
  version: version,
  auth: {
    audience: 'https://cube.jax.org',
    domain: 'thejacksonlaboratory.auth0.com',
    clientId: '0w63zAu6qchS85N6KwIw9Z0Nqw9Z8Bsn',
  },
  urls: {
    geneWeaver: 'https://geneweaver.jax.org',
    pubmed: 'https://pubmed.ncbi.nlm.nih.gov',
  }
};

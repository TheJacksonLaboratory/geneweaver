import { Environment } from './environment-interface';
import { environment as defaultEnvironment } from './environment.default';

export const environment: Environment = {
  ...defaultEnvironment,
  auth: {
    audience: 'https://cube.jax.org',
    domain: 'thejacksonlaboratory.auth0.com',
    clientId: '0w63zAu6qchS85N6KwIw9Z0Nqw9Z8Bsn',
  },
  urls: {
    geneWeaver: 'https://geneweaver.jax.org',
  }
};

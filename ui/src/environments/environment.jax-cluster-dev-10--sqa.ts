import { Environment } from './environment-interface';
import { environment as defaultEnvironment } from './environment.default';

export const environment: Environment = {
  ...defaultEnvironment,
  urls: {
    geneWeaver: 'https://geneweaver-sqa.jax.org',
  },
};

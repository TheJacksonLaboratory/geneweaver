import { Environment } from './environment-interface';
import packageJson from '../../package.json';

// This default environment is used for tests in the build pipeline
export const environment: Environment = {
    production: false,
    version: packageJson.version,
    auth: {
        audience: 'https://cube.jax.org',
        domain: 'thejacksonlaboratory.auth0.com',
        clientId: 'SrKiPbqYqWbfAZODolg2gwgcAtAs0ZmY',
    },
    urls: {
        geneWeaver: 'https://geneweaver-dev.jax.org',
    },
    features: {}
};



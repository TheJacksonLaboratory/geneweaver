import { Environment } from './environment-interface';

// This default environment is used for tests in the build pipeline
export const environment: Environment = {
    production: false,
    version: '0.0.0.test',
    auth: {
        audience: 'https://cube.jax.org',
        domain: 'thejacksonlaboratory.auth0.com',
        clientId: 'SrKiPbqYqWbfAZODolg2gwgcAtAs0ZmY',
    },
    urls: {
        geneWeaver: 'https://geneweaver-dev.jax.org',
    },
    features: {
        geneSetDetailsPage: false
    }
};

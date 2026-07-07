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
        // Local dev default (used by `nx serve`): the locally-running API.
        geneWeaverApi: 'http://127.0.0.1:8000/api',
        pubmed: 'https://pubmed.ncbi.nlm.nih.gov',
    },
    features: {
        geneSetDetailsPage: false
    }
};

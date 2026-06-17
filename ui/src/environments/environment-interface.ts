export interface Environment {
    production: boolean;
    version: string;
    auth: {
        audience: string;
        domain: string;
        clientId: string;
    };
    urls: {
        geneWeaver: string;
        geneWeaverApi: string;
        pubmed: string;
    };
    // feature flag
    features: FeatureFlags
}

export interface FeatureFlags {
    // Populate this interface once there are features to flag.
    geneSetDetailsPage: boolean;
}
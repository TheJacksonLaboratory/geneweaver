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
    };
    // feature flag
    features: FeatureFlags
}

export interface FeatureFlags {

}
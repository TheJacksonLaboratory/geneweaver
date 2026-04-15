import { Environment } from './environment-interface';
import { environment as defaultEnvironment } from './environment.default';

export const environment: Environment = {
    ...defaultEnvironment,
    version: '0.0.0'
};

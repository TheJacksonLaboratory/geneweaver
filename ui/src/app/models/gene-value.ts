export interface GeneValue {
    gs_id: number,
    ode_gene_id: number,
    gsv_value: number,
    gsv_hits: number,
    gsv_source_list: string[],
    gsv_value_list: number[],
    gsv_in_threshold: boolean,
    gsv_date: string,
    ode_ref_id: number
}

export interface SimpleGeneValue {
    symbol: string,
    value: number
}

export enum GeneIdTypes {
    GENE_SYMBOL = 'Gene Symbol',
    ENTREZ = 'Entrez',
    ENSEMBL_GENE = 'Ensemble Gene',
    UNIGENE = 'Unigene',
    MGI = 'MGI',
    FLYBASE = 'FlyBase',
    WORMBASE = 'Wormbase',
    RGD = 'RGD',
    ZFIN = 'ZFIN'
}

export class GeneValueDownload {
    gs_id: any;
    gsv_source_list: any;
    gsv_value: any;
    ode_ref_id: any;
}
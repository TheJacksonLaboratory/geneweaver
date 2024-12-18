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
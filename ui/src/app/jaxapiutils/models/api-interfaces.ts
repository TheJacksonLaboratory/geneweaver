export interface PagingLinks {
    first?: string;
    previous?: string;
    next?: string;
    last?: string;
}

export interface Paging {
    page?: number;
    items?: number;
    total_pages?: number;
    total_items?: number;
    links?: PagingLinks;
}

export interface Error {
    code: number;
    message: string;
}

export interface BaseResponse {
    errors?: Error[];
    info?: Record<string, any>;
}

export interface Response<T> extends BaseResponse {
    object?: T;
}

export interface CollectionResponse<T> extends BaseResponse {
    data: T[];
    paging?: Paging;
}
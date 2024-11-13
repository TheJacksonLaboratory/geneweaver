import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Response, CollectionResponse } from '../models/api-interfaces';

@Injectable({
    providedIn: 'root'
})
export class APIBaseService {
    private baseUrl: string = 'https://geneweaver.jax.org/api';

    constructor(private http: HttpClient) {}

    /**
     * Get a single resource
     * @param url The endpoint URL
     * @param params Optional query parameters
     */
    get<T>(url: string, params?: HttpParams): Observable<Response<T>> {
        return this.http.get<Response<T>>(`${this.baseUrl}${url}`, { params });
    }

    /**
     * Get a collection of resources
     * @param url The endpoint URL
     * @param params Optional query parameters
     */
    getCollection<T>(url: string, params?: HttpParams): Observable<CollectionResponse<T>> {
        return this.http.get<CollectionResponse<T>>(`${this.baseUrl}${url}`, { params });
    }

    /**
     * Create a new resource
     * @param url The endpoint URL
     * @param body The resource to create
     */
    post<T>(url: string, body: any): Observable<Response<T>> {
        return this.http.post<Response<T>>(`${this.baseUrl}${url}`, body);
    }

    /**
     * Update an existing resource
     * @param url The endpoint URL
     * @param body The resource updates
     */
    put<T>(url: string, body: any): Observable<Response<T>> {
        return this.http.put<Response<T>>(`${this.baseUrl}${url}`, body);
    }

    /**
     * Partially update an existing resource
     * @param url The endpoint URL
     * @param body The partial resource updates
     */
    patch<T>(url: string, body: any): Observable<Response<T>> {
        return this.http.patch<Response<T>>(`${this.baseUrl}${url}`, body);
    }

    /**
     * Delete a resource
     * @param url The endpoint URL
     */
    delete<T>(url: string): Observable<Response<T>> {
        return this.http.delete<Response<T>>(`${this.baseUrl}${url}`);
    }
}
import { Paging, PagingLinks } from '../models/api-interfaces';

export class PagingUtils {
    /**
     * Extract page number from a paging URL
     * @param url The paging URL to parse
     */
    static getPageFromUrl(url: string): number | null {
        try {
            const urlObj = new URL(url);
            const page = urlObj.searchParams.get('page');
            return page ? parseInt(page, 10) : null;
        } catch {
            return null;
        }
    }

    /**
     * Check if there are more pages available
     * @param paging The paging information
     */
    static hasNextPage(paging: Paging): boolean {
        return !!paging.links?.next;
    }

    /**
     * Check if there are previous pages available
     * @param paging The paging information
     */
    static hasPreviousPage(paging: Paging): boolean {
        return !!paging.links?.previous;
    }
}
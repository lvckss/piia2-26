import sql from '../bd/bd';
import { type PostInstance, type Instance, InstanceSchema } from '../models/Instance';

export const getInstances = async (): Promise<Instance[]> => {
    const results = await sql`SELECT * FROM instancias`;
    return results.map((result: any) => InstanceSchema.parse(result))
}
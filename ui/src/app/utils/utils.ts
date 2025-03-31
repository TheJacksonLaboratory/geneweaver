

// Convert model from one type to another with a variation of the same properties
export function convertModel<T, U>(source: T, targetConstructor: new () => U): U {
  const target = new targetConstructor();

  for (const key in source) {
    if (Object.prototype.hasOwnProperty.call(source, key) && Object.prototype.hasOwnProperty.call(target, key)) {
      (target as any)[key] = (source as any)[key];
    }
  }
  return target;
}
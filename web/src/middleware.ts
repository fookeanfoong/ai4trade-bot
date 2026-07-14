import createMiddleware from 'next-intl/middleware';
import { routing } from './i18n/routing';

export default createMiddleware(routing);

export const config = {
  // 匹配所有路径,排除 api / _next / 静态资源
  matcher: ['/((?!api|_next|_vercel|logos|.*\\..*).*)'],
};

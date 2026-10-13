import { MainPageView } from '@/components/MainPageView'
import { useMainPageController } from '@/hooks/useMainPageController'

export function MainPage(): React.JSX.Element {
  const viewProps = useMainPageController()
  return <MainPageView {...viewProps} />
}

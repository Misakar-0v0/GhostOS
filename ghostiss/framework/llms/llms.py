from typing import Optional, Dict, Iterator, Tuple, List
from os import environ

from ghostiss.blueprint.kernel.llms import LLMs, LLMApi, ServiceConf, ModelConf, LLMDriver, LLMsConfig

__all__ = ['LLMsImpl']


class LLMsImpl(LLMs):
    """
    实现 LLMs
    """

    def __init__(
            self,
            *,
            conf: Optional[LLMsConfig],
            default_driver: LLMDriver,
            drivers: Optional[List[LLMDriver]] = None,
    ):
        self._llm_drivers: Dict[str, LLMDriver] = {}
        self._llm_services: Dict[str, ServiceConf] = {}
        self._llm_models: Dict[str, ModelConf] = {}
        self._default_driver = default_driver
        self._apis: Dict[str, LLMApi] = {}

        if drivers:
            for driver in drivers:
                self.register_driver(driver)
        if conf:
            for service in conf.services:
                self.register_service(service)
            for name, model in conf.models.items():
                self.register_model(name, model)

    def register_driver(self, driver: LLMDriver) -> None:
        self._llm_drivers[driver.driver_name()] = driver

    def register_service(self, service: ServiceConf) -> None:
        if not service.token:
            service.token = self._get_token(service.token_key)
        self._llm_services[service.name] = service

    @staticmethod
    def _get_token(token_key: str) -> str:
        """
        默认使用 env 来获取.
        """
        return environ.get(token_key)

    def register_model(self, name: str, model_conf: ModelConf) -> None:
        self._llm_models[name] = model_conf

    def services(self) -> List[ServiceConf]:
        return list(self._llm_services.values())

    def each_api_conf(self) -> Iterator[Tuple[ServiceConf, ModelConf]]:
        for model_conf in self._llm_models.values():
            service = self._llm_services.get(model_conf.service, None)
            if service is None:
                # todo: 似乎要 fail.
                continue
            yield service, model_conf

    def new_api(self, service_conf: ServiceConf, api_conf: ModelConf) -> LLMApi:
        driver = self._llm_drivers.get(service_conf.driver, self._default_driver)
        return driver.new(service_conf, api_conf)

    def get_api(self, api_name: str, trace: Optional[Dict] = None) -> Optional[LLMApi]:
        api = self._apis.get(api_name, None)
        if api is not None:
            return api
        model_conf = self._llm_models.get(api_name, None)
        if model_conf is None:
            return None
        service_conf = self._llm_services.get(model_conf.service, None)
        if service_conf is None:
            return None
        api = self.new_api(service_conf, model_conf)
        # 解决缓存问题. 工业场景中, 或许不该缓存, 因为配置随时可能变化.
        if api is not None:
            self._apis[api_name] = api
            return api
        return None
